"""Автоматический демо-сценарий для презентации бота."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from shared.config import get_settings
from shared.service_auth import internal_service_headers


DEMO_TELEGRAM_USER_ID = "999000001"
DEMO_CHAT_ID = "999000001"


def _debug_headers(admin_token: str = "") -> dict[str, str]:
    settings = get_settings()
    token = settings.debug_api_token or settings.admin_token or admin_token
    return {"X-Debug-Token": token} if token else {}


def _service_headers(**extra: str) -> dict[str, str]:
    return internal_service_headers(**extra)


def _patient_headers(telegram_user_id: str = DEMO_TELEGRAM_USER_ID) -> dict[str, str]:
    return internal_service_headers(telegram_user_id=telegram_user_id)


@dataclass
class DemoStep:
    name: str
    ok: bool
    detail: str
    payload: dict[str, Any] = field(default_factory=dict)


async def run_demo_scenario(
    core_api_url: str,
    bot_gateway_url: str,
    ai_orchestrator_url: str,
    *,
    admin_token: str = "",
    skip_reset: bool = False,
) -> dict[str, Any]:
    steps: list[DemoStep] = []
    base_core = core_api_url.rstrip("/")
    base_bot = bot_gateway_url.rstrip("/")
    base_ai = ai_orchestrator_url.rstrip("/")

    async with httpx.AsyncClient(timeout=15) as client:
        if not skip_reset:
            headers = {"X-Admin-Token": admin_token} if admin_token else {}
            try:
                response = await client.post(f"{base_core}/api/admin/demo/reset", headers=headers)
                response.raise_for_status()
                steps.append(DemoStep("Сброс демо-данных", True, "База подготовлена", response.json()))
            except Exception as exc:
                steps.append(DemoStep("Сброс демо-данных", False, str(exc)))
        steps.append(await _step_register(client, base_core))
        steps.append(await _step_ai_intake(client, base_ai))
        steps.append(await _step_bot_start(client, base_bot))
        steps.append(await _step_book_via_bot(client, base_bot, base_core))
        steps.append(await _step_clinical_refusal(client, base_ai))
        steps.append(await _step_unknown_service(client, base_ai))
        steps.append(await _step_list_appointments(client, base_bot))

    success = all(step.ok for step in steps)
    return {
        "success": success,
        "telegramUserId": DEMO_TELEGRAM_USER_ID,
        "steps": [
            {"name": s.name, "ok": s.ok, "detail": s.detail, "payload": s.payload} for s in steps
        ],
    }


async def _step_register(client: httpx.AsyncClient, core_api_url: str) -> DemoStep:
    try:
        response = await client.post(
            f"{core_api_url}/api/patients/quick-register",
            headers=_service_headers(telegram_user_id=DEMO_TELEGRAM_USER_ID),
            json={
                "telegram_user_id": DEMO_TELEGRAM_USER_ID,
                "chat_id": DEMO_CHAT_ID,
                "name": "Демо Клиент",
                "username": "demo_client",
            },
        )
        response.raise_for_status()
        data = response.json()
        return DemoStep(
            "Быстрая регистрация",
            True,
            f"Пациент {data.get('name')} создан",
            data,
        )
    except Exception as exc:
        return DemoStep("Быстрая регистрация", False, str(exc))


async def _step_ai_intake(client: httpx.AsyncClient, ai_url: str) -> DemoStep:
    try:
        response = await client.post(
            f"{ai_url}/api/ai/intake",
            headers=_service_headers(telegram_user_id=DEMO_TELEGRAM_USER_ID),
            json={
                "telegram_user_id": DEMO_TELEGRAM_USER_ID,
                "text": "Болит зуб слева уже неделю",
            },
        )
        response.raise_for_status()
        data = response.json()
        slots = [b for b in data.get("buttons", []) if b.get("callback_data", "").startswith("slot:")]
        ok = data.get("intent") == "appointment_intake" and len(slots) > 0
        return DemoStep(
            "AI intake по жалобе",
            ok,
            f"Intent: {data.get('intent')}, слотов: {len(slots)}",
            {"intent": data.get("intent"), "route": data.get("route"), "slotButtons": len(slots)},
        )
    except Exception as exc:
        return DemoStep("AI intake по жалобе", False, str(exc))


async def _step_bot_start(client: httpx.AsyncClient, bot_url: str) -> DemoStep:
    try:
        response = await client.post(
            f"{bot_url}/debug/simulate",
            headers=_debug_headers(),
            json={
                "message": {
                    "chat": {"id": int(DEMO_CHAT_ID)},
                    "from": {"id": int(DEMO_TELEGRAM_USER_ID), "first_name": "Демо", "username": "demo_client"},
                    "text": "/start",
                }
            },
        )
        response.raise_for_status()
        data = response.json()
        ok = "Демо стоматология" in data.get("text", "") or "Записаться" in str(data.get("buttons", []))
        return DemoStep("Бот /start", ok, data.get("text", "")[:120], {"text": data.get("text")})
    except Exception as exc:
        return DemoStep("Бот /start", False, str(exc))


async def _step_book_via_bot(client: httpx.AsyncClient, bot_url: str, core_api_url: str) -> DemoStep:
    try:
        slots_response = await client.get(
            f"{core_api_url}/api/schedule/slots/available",
            headers=_service_headers(),
            params={"service_id": "svc_primary", "limit": 1},
        )
        slots_response.raise_for_status()
        slots = slots_response.json()
        if not slots:
            return DemoStep("Запись через кнопку слота", False, "Нет свободных слотов")
        slot_id = slots[0]["slot_id"]
        await client.post(
            f"{bot_url}/debug/simulate",
            headers=_debug_headers(),
            json={
                "callback_query": {
                    "id": "demo-0",
                    "from": {"id": int(DEMO_TELEGRAM_USER_ID), "username": "demo_client"},
                    "message": {"chat": {"id": int(DEMO_CHAT_ID)}},
                    "data": "service:select:svc_primary",
                }
            },
        )
        simulate = await client.post(
            f"{bot_url}/debug/simulate",
            headers=_debug_headers(),
            json={
                "callback_query": {
                    "id": "demo-1",
                    "from": {"id": int(DEMO_TELEGRAM_USER_ID), "username": "demo_client"},
                    "message": {"chat": {"id": int(DEMO_CHAT_ID)}},
                    "data": f"slot:select:{slot_id}",
                }
            },
        )
        simulate.raise_for_status()
        screen = simulate.json()
        patient = await client.post(
            f"{core_api_url}/api/patients/lookup",
            headers=_service_headers(telegram_user_id=DEMO_TELEGRAM_USER_ID),
            json={"telegram_user_id": DEMO_TELEGRAM_USER_ID},
        )
        patient.raise_for_status()
        appointments = await client.get(
            f"{core_api_url}/api/appointments/patient/{patient.json()['patient_id']}",
            headers=_patient_headers(),
        )
        appointments.raise_for_status()
        items = appointments.json()
        ok = len(items) > 0 and "подтверждена" in screen.get("text", "").lower()
        return DemoStep(
            "Запись через кнопку слота",
            ok,
            screen.get("text", ""),
            {"appointmentCount": len(items), "slotId": slot_id},
        )
    except Exception as exc:
        return DemoStep("Запись через кнопку слота", False, str(exc))


async def _step_clinical_refusal(client: httpx.AsyncClient, ai_url: str) -> DemoStep:
    try:
        response = await client.post(
            f"{ai_url}/api/ai/intake",
            headers=_service_headers(telegram_user_id=DEMO_TELEGRAM_USER_ID),
            json={"telegram_user_id": DEMO_TELEGRAM_USER_ID, "text": "Что у меня за болезнь?"},
        )
        response.raise_for_status()
        data = response.json()
        ok = data.get("intent") == "clinical_question" and "диагноз" in data.get("text", "").lower()
        return DemoStep("Отказ от диагноза", ok, data.get("text", "")[:120], {"intent": data.get("intent")})
    except Exception as exc:
        return DemoStep("Отказ от диагноза", False, str(exc))


async def _step_unknown_service(client: httpx.AsyncClient, ai_url: str) -> DemoStep:
    try:
        response = await client.post(
            f"{ai_url}/api/ai/intake",
            headers=_service_headers(telegram_user_id=DEMO_TELEGRAM_USER_ID),
            json={"telegram_user_id": DEMO_TELEGRAM_USER_ID, "text": "Хочу имплантацию"},
        )
        response.raise_for_status()
        data = response.json()
        ok = data.get("intent") == "unknown_service"
        return DemoStep(
            "Неизвестная услуга",
            ok,
            data.get("text", "")[:120],
            {"intent": data.get("intent")},
        )
    except Exception as exc:
        return DemoStep("Неизвестная услуга", False, str(exc))


async def _step_list_appointments(client: httpx.AsyncClient, bot_url: str) -> DemoStep:
    try:
        response = await client.post(
            f"{bot_url}/debug/simulate",
            headers=_debug_headers(),
            json={
                "callback_query": {
                    "id": "demo-2",
                    "from": {"id": int(DEMO_TELEGRAM_USER_ID), "username": "demo_client"},
                    "message": {"chat": {"id": int(DEMO_CHAT_ID)}},
                    "data": "appointment:list",
                }
            },
        )
        response.raise_for_status()
        data = response.json()
        ok = "запис" in data.get("text", "").lower()
        return DemoStep("Мои записи в боте", ok, data.get("text", "")[:120], {"text": data.get("text")})
    except Exception as exc:
        return DemoStep("Мои записи в боте", False, str(exc))
