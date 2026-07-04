import asyncio
import logging
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request

from services.bot_gateway.rendering import (
    appointments_screen,
    contacts_screen,
    main_menu,
    pricing_screen,
    registration_done_screen,
    services_screen,
    simple_screen,
    slots_screen,
    to_telegram_markup,
    welcome_screen,
)
from shared.callbacks import parse_callback
from shared.config import get_settings
from shared.schemas import Button, IntakeResponse, Screen
from shared.security import SlidingWindowRateLimiter, rate_limit_request, verify_webhook_secret
from shared.telegram_client import create_telegram_bot, httpx_async_client

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
app = FastAPI(title="Dental Telegram Bot Gateway", version="0.1.0")
limiter = SlidingWindowRateLimiter(limit=60, window_seconds=60)
logger = logging.getLogger(__name__)

try:
    from aiogram import Bot
except ModuleNotFoundError:
    Bot = None

bot = create_telegram_bot()
STATE: dict[str, dict[str, Any]] = {}
AI_CALL_COUNT = 0
POLLING_TASK: asyncio.Task | None = None
POLLING_STOP = asyncio.Event()


async def poll_telegram_updates() -> None:
    if not settings.telegram_bot_token:
        return
    base = settings.telegram_api_base.rstrip("/")
    token = settings.telegram_bot_token
    updates_url = f"{base}/bot{token}/getUpdates"
    offset = 0
    logger.info(
        "Telegram long polling started%s",
        f" via proxy {settings.telegram_proxy_url}" if settings.telegram_proxy_url else "",
    )
    async with httpx_async_client(timeout=60) as client:
        await client.post(
            f"{base}/bot{token}/deleteWebhook",
            json={"drop_pending_updates": True},
        )
        while not POLLING_STOP.is_set():
            try:
                response = await client.get(
                    updates_url,
                    params={"offset": offset, "timeout": 30},
                )
                response.raise_for_status()
                payload = response.json()
                if not payload.get("ok"):
                    logger.warning("getUpdates returned error: %s", payload)
                    await asyncio.sleep(3)
                    continue
                for update in payload.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        await handle_update(update, send=True)
                    except Exception:
                        logger.exception("Failed to handle Telegram update %s", update.get("update_id"))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Telegram polling error: %s", exc)
                await asyncio.sleep(5)


@app.on_event("startup")
async def startup() -> None:
    global POLLING_TASK
    mode = settings.telegram_mode.lower().strip()
    if mode == "polling":
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is empty; polling not started")
            return
        POLLING_STOP.clear()
        POLLING_TASK = asyncio.create_task(poll_telegram_updates())
        return

    webhook_url = settings.telegram_webhook_url.strip()
    if not bot or not webhook_url:
        return
    if "your-ngrok-url" in webhook_url or "your-public-url" in webhook_url:
        logger.warning("TELEGRAM_WEBHOOK_URL is a placeholder; webhook not registered on startup")
        return
    try:
        await bot.set_webhook(
            webhook_url,
            secret_token=settings.telegram_webhook_secret or None,
            drop_pending_updates=True,
            request_timeout=10,
        )
        logger.info("Telegram webhook registered: %s", webhook_url)
    except Exception as exc:
        logger.warning("Failed to register Telegram webhook on startup: %s", exc)


@app.on_event("shutdown")
async def shutdown() -> None:
    global POLLING_TASK
    POLLING_STOP.set()
    if POLLING_TASK:
        POLLING_TASK.cancel()
        try:
            await POLLING_TASK
        except asyncio.CancelledError:
            pass
        POLLING_TASK = None
    if bot:
        await bot.session.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/debug/ai-call-count")
def ai_call_count() -> dict[str, int]:
    return {"count": AI_CALL_COUNT}


@app.post("/api/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    verify_webhook_secret(settings.telegram_webhook_secret, x_telegram_bot_api_secret_token)
    await rate_limit_request(request, limiter)
    update = await request.json()
    screen = await handle_update(update)
    return {"ok": True, "screen": screen.model_dump(mode="json") if screen else None}


@app.post("/debug/simulate", response_model=Screen)
async def simulate_update(update: dict) -> Screen:
    screen = await handle_update(update, send=False)
    if not screen:
        raise HTTPException(status_code=400, detail="Unsupported update")
    return screen


async def handle_update(update: dict, send: bool = True) -> Screen | None:
    if "message" in update:
        message = update["message"]
        chat_id = str(message["chat"]["id"])
        from_user = message.get("from", {})
        telegram_user_id = str(from_user.get("id", chat_id))
        text = (message.get("text") or "").strip()
        await _register_user(telegram_user_id, chat_id, from_user.get("username"))
        if message.get("contact"):
            return await _quick_register(
                telegram_user_id,
                chat_id,
                from_user,
                send,
                phone=message["contact"].get("phone_number"),
            )
        if text.startswith("/start"):
            if await _is_registered(telegram_user_id):
                return await _respond(chat_id, main_menu(), send)
            return await _respond(chat_id, welcome_screen(_display_name(from_user)), send)
        if not await _is_registered(telegram_user_id):
            return await _respond(chat_id, welcome_screen(_display_name(from_user)), send)
        return await _handle_text(telegram_user_id, chat_id, text, send)

    if "callback_query" in update:
        callback = update["callback_query"]
        data = callback.get("data", "")
        message = callback.get("message", {})
        chat_id = str(message.get("chat", {}).get("id"))
        from_user = callback.get("from", {})
        telegram_user_id = str(from_user.get("id", chat_id))
        if send and bot:
            try:
                await bot.answer_callback_query(callback_query_id=callback.get("id"))
            except Exception:
                logger.debug("answerCallbackQuery failed", exc_info=True)
        await _register_user(telegram_user_id, chat_id, from_user.get("username"))
        return await _handle_callback(telegram_user_id, chat_id, data, send, from_user)
    return None


async def _handle_text(telegram_user_id: str, chat_id: str, text: str, send: bool) -> Screen:
    global AI_CALL_COUNT
    AI_CALL_COUNT += 1
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(
            f"{settings.ai_orchestrator_url}/api/ai/intake",
            json={"telegram_user_id": telegram_user_id, "text": text},
        )
        response.raise_for_status()
    screen = IntakeResponse.model_validate(response.json())
    if screen.conversation_state:
        STATE[telegram_user_id] = screen.conversation_state
    return await _respond(chat_id, screen, send)


PUBLIC_CALLBACKS = {
    "pricing:list",
    "menu:contacts",
    "menu:main",
    "nav:back",
    "calendar:doctor:today",
}


async def _handle_callback(
    telegram_user_id: str,
    chat_id: str,
    data: str,
    send: bool,
    from_user: dict | None = None,
) -> Screen:
    action = parse_callback(data)
    if data == "menu:main":
        return await _respond(chat_id, main_menu(), send)
    if data == "menu:contacts":
        return await _respond(chat_id, contacts_screen(settings.clinic_phone), send)
    if data == "nav:back":
        return await _respond(chat_id, main_menu(), send)
    if action.namespace == "register" and action.action == "confirm":
        if not from_user:
            return await _respond(chat_id, welcome_screen(), send)
        return await _quick_register(telegram_user_id, chat_id, from_user, send)
    if not await _is_registered(telegram_user_id) and data not in PUBLIC_CALLBACKS:
        return await _respond(chat_id, welcome_screen(_display_name(from_user or {})), send)
    if data == "appointment:start":
        return await _show_services(chat_id, send)
    if data == "appointment:list":
        return await _show_patient_appointments(telegram_user_id, chat_id, send)
    if data == "pricing:list":
        return await _show_pricing(chat_id, send)
    if data == "calendar:doctor:today":
        return await _show_doctor_calendar(chat_id, send)
    if action.namespace == "service" and action.action == "select":
        return await _show_slots(chat_id, action.args[0], send)
    if action.namespace == "slot" and action.action == "select":
        return await _commit_slot(telegram_user_id, chat_id, action.args[0], send)
    if action.namespace == "appointment" and action.action == "cancel":
        return await _cancel_appointment(chat_id, action.args[0], send)
    if action.namespace == "reschedule" and action.action == "start":
        return await _show_reschedule_slots(chat_id, action.args[0], send)
    if action.namespace == "reschedule" and action.action == "slot":
        return await _commit_patient_reschedule(chat_id, action.args[0], action.args[1], send)
    if action.namespace == "reschedule" and action.action == "approve":
        return await _approve_reschedule(chat_id, action.args[0], send)
    if action.namespace == "reschedule" and action.action == "reject":
        return await _reject_reschedule(chat_id, action.args[0], send)
    return await _respond(chat_id, main_menu(), send)


async def _show_services(chat_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{settings.core_api_url}/api/services")
        response.raise_for_status()
    return await _respond(chat_id, services_screen(response.json()), send)


async def _show_slots(chat_id: str, service_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(
            f"{settings.core_api_url}/api/schedule/slots/available",
            params={"service_id": service_id, "limit": 6},
        )
        response.raise_for_status()
    return await _respond(chat_id, slots_screen(response.json(), service_id), send)


async def _commit_slot(telegram_user_id: str, chat_id: str, slot_id: str, send: bool) -> Screen:
    state = STATE.get(telegram_user_id, {})
    doctor_id = state.get("doctorId") or _doctor_from_slot_id(slot_id)
    service_id = state.get("serviceId") or ("svc_extraction" if doctor_id == "doc_surgeon" else "svc_primary")
    visit_type = state.get("visitType") or "primary_consultation"
    async with httpx.AsyncClient(timeout=8) as client:
        patient = await client.post(
            f"{settings.core_api_url}/api/patients/lookup",
            json={"telegram_user_id": telegram_user_id},
        )
        patient.raise_for_status()
        response = await client.post(
            f"{settings.core_api_url}/api/appointments",
            headers={"Idempotency-Key": f"appointment-create:{telegram_user_id}:{slot_id}"},
            json={
                "patient_id": patient.json()["patient_id"],
                "doctor_id": doctor_id,
                "service_id": service_id,
                "slot_id": slot_id,
                "visit_type": visit_type,
            },
        )
    if response.status_code == 409:
        return await _respond(
            chat_id,
            simple_screen(
                "Этот слот уже занят. Выберите другое время.",
                [Button(text="Выбрать слот", callback_data="appointment:start")],
            ),
            send,
        )
    response.raise_for_status()
    appointment = response.json()
    screen = simple_screen(
        f"Запись подтверждена\n\n{appointment['date']}  {appointment['time'][:5]}",
        [
            Button(text="Мои записи", callback_data="appointment:list"),
        ],
        layout=[1],
    )
    return await _respond(chat_id, screen, send)


async def _show_patient_appointments(telegram_user_id: str, chat_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=5) as client:
        patient = await client.post(
            f"{settings.core_api_url}/api/patients/lookup",
            json={"telegram_user_id": telegram_user_id},
        )
        patient.raise_for_status()
        response = await client.get(
            f"{settings.core_api_url}/api/appointments/patient/{patient.json()['patient_id']}"
        )
        response.raise_for_status()
    appointments = response.json()
    if not appointments:
        return await _respond(
            chat_id,
            simple_screen(
                "Активных записей нет.",
                [Button(text="Записаться", callback_data="appointment:start")],
            ),
            send,
        )
    action_buttons = []
    lines = []
    for item in appointments:
        label = f"{item['date']}  {item['time'][:5]}"
        lines.append(label)
        action_buttons.append(
            Button(text=f"Перенести · {item['time'][:5]}", callback_data=f"reschedule:start:{item['appointment_id']}")
        )
        action_buttons.append(
            Button(text=f"Отменить · {item['time'][:5]}", callback_data=f"appointment:cancel:{item['appointment_id']}")
        )
    screen = appointments_screen(lines, action_buttons)
    screen.button_layout = [2] * (len(action_buttons) // 2) + [2]
    return await _respond(chat_id, screen, send)


async def _show_reschedule_slots(chat_id: str, appointment_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{settings.core_api_url}/api/schedule/slots/available", params={"limit": 6})
        response.raise_for_status()
    buttons = [
        Button(
            text=f"{slot['date']}  {slot['time'][:5]}",
            callback_data=f"reschedule:slot:{appointment_id}:{slot['slot_id']}",
        )
        for slot in response.json()
    ]
    screen = slots_screen([], appointment_id)
    screen = screen.model_copy(
        update={
            "text": "Перенос записи\n\nВыберите новый слот:",
            "buttons": buttons + screen.buttons[-2:],
            "conversation_state": {},
        }
    )
    return await _respond(chat_id, screen, send)


async def _commit_patient_reschedule(chat_id: str, appointment_id: str, slot_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(
            f"{settings.core_api_url}/api/appointments/{appointment_id}/reschedule/by-patient",
            headers={"Idempotency-Key": f"reschedule-patient:{appointment_id}:{slot_id}"},
            json={"new_slot_id": slot_id},
        )
        response.raise_for_status()
    item = response.json()
    return await _respond(
        chat_id,
        simple_screen(f"Запись перенесена\n\n{item['date']}  {item['time'][:5]}", [Button(text="Мои записи", callback_data="appointment:list")]),
        send,
    )


async def _cancel_appointment(chat_id: str, appointment_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(
            f"{settings.core_api_url}/api/appointments/{appointment_id}/cancel",
            headers={"Idempotency-Key": f"cancel:{appointment_id}"},
        )
        response.raise_for_status()
    return await _respond(chat_id, simple_screen("Запись отменена."), send)


async def _approve_reschedule(chat_id: str, approval_request_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(f"{settings.core_api_url}/api/reschedule/{approval_request_id}/approve")
        response.raise_for_status()
    item = response.json()
    return await _respond(
        chat_id,
        simple_screen(f"Перенос одобрен\n\n{item['date']}  {item['time'][:5]}"),
        send,
    )


async def _reject_reschedule(chat_id: str, approval_request_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(f"{settings.core_api_url}/api/reschedule/{approval_request_id}/reject")
        response.raise_for_status()
    return await _respond(chat_id, simple_screen("Перенос отклонён. Текущая запись сохранена."), send)


async def _show_pricing(chat_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{settings.core_api_url}/api/services")
        response.raise_for_status()
    lines = []
    for item in response.json():
        lines.append(f"{item['name']} — {item['price']} {item['currency']}")
    return await _respond(chat_id, pricing_screen(lines), send)


async def _show_doctor_calendar(chat_id: str, send: bool) -> Screen:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(
            f"{settings.core_api_url}/api/calendar/doctor/doc_therapist",
            headers={"X-Role": "doctor"},
        )
        response.raise_for_status()
    lines = []
    for item in response.json():
        lines.append(f"{item['date']}  {item['time'][:5]}")
    if not lines:
        lines.append("Записей пока нет.")
    return await _respond(
        chat_id,
        simple_screen("Календарь врача\n\n" + "\n".join(lines)),
        send,
    )


async def _is_registered(telegram_user_id: str) -> bool:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{settings.core_api_url}/api/patients/by-telegram/{telegram_user_id}")
    return response.status_code == 200


async def _quick_register(
    telegram_user_id: str,
    chat_id: str,
    from_user: dict,
    send: bool,
    phone: str | None = None,
) -> Screen:
    name = _display_name(from_user)
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(
            f"{settings.core_api_url}/api/patients/quick-register",
            json={
                "telegram_user_id": telegram_user_id,
                "chat_id": chat_id,
                "name": name,
                "username": from_user.get("username"),
                "phone": phone,
            },
        )
        response.raise_for_status()
    return await _respond(chat_id, registration_done_screen(name), send)


def _display_name(from_user: dict) -> str:
    parts = [from_user.get("first_name"), from_user.get("last_name")]
    name = " ".join(part for part in parts if part)
    return name or from_user.get("username") or "Пациент"


async def _register_user(telegram_user_id: str, chat_id: str, username: str | None) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{settings.core_api_url}/api/users/telegram/register",
            json={
                "telegram_user_id": telegram_user_id,
                "chat_id": chat_id,
                "username": username,
                "role": "patient",
            },
        )


async def _respond(chat_id: str, screen: Screen, send: bool) -> Screen:
    if send and bot and chat_id:
        await bot.send_message(
            chat_id=chat_id,
            text=screen.text,
            reply_markup=to_telegram_markup(screen),
        )
    return screen


def _doctor_from_slot_id(slot_id: str) -> str:
    parts = slot_id.split("_")
    if len(parts) >= 4:
        return "_".join(parts[1:-2])
    return "doc_therapist"


if __name__ == "__main__":
    uvicorn.run("services.bot_gateway.main:app", host="0.0.0.0", port=8080)
