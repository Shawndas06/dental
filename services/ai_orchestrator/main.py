import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import httpx

from services.ai_orchestrator.cks import classify_text, route_text
from services.ai_orchestrator.safety import (
    is_clinical_question,
    low_confidence_fallback,
    safe_refusal,
    unknown_service_refusal,
    validate_ai_screen,
)
from shared.callbacks import build_callback
from shared.config import get_settings
from shared.schemas import Button, IntakeRequest, IntakeResponse
from shared.security import SlidingWindowRateLimiter, safe_compare_digest
from shared.service_auth import internal_service_headers

settings = get_settings()
app = FastAPI(title="Dental AI Orchestrator", version="0.1.0")
intake_limiter = SlidingWindowRateLimiter(limit=30, window_seconds=60)


@app.middleware("http")
async def enforce_internal_service_token(request: Request, call_next):
    path = request.url.path
    if path == "/health":
        return await call_next(request)
    if path.startswith("/api/"):
        expected = settings.internal_service_token
        if not expected or not safe_compare_digest(
            request.headers.get("X-Service-Token", ""),
            expected,
        ):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid service token"},
            )
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ai/intake", response_model=IntakeResponse)
async def intake(payload: IntakeRequest) -> IntakeResponse:
    if not intake_limiter.allow(payload.telegram_user_id):
        return low_confidence_fallback()

    if is_clinical_question(payload.text):
        return safe_refusal()

    intent = classify_text(payload.text)
    if intent == "clinical_question":
        return safe_refusal()
    if intent == "unknown_service":
        return unknown_service_refusal()
    if intent == "low_confidence":
        return low_confidence_fallback()

    route = route_text(payload.text)
    headers = internal_service_headers(telegram_user_id=payload.telegram_user_id)
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{settings.core_api_url}/api/patients/lookup",
            headers=headers,
            json={
                "telegram_user_id": payload.telegram_user_id,
                "phone": payload.phone,
            },
        )
        services_response = await client.get(
            f"{settings.core_api_url}/api/services",
            headers=headers,
        )
        slots_response = await client.get(
            f"{settings.core_api_url}/api/schedule/slots/available",
            headers=headers,
            params={"doctor_id": route.doctor_id, "service_id": route.service_id, "limit": 4},
        )
    services_response.raise_for_status()
    slots_response.raise_for_status()

    services = services_response.json()
    slots = slots_response.json()
    allowed_service_ids = {item["service_id"] for item in services}
    allowed_slot_ids = {item["slot_id"] for item in slots}
    if route.service_id not in allowed_service_ids:
        return unknown_service_refusal()
    if not slots:
        return IntakeResponse(
            intent="appointment_intake",
            confidence=route.confidence,
            text="Свободных слотов по этому направлению сейчас нет. Можно выбрать другой сценарий.",
            buttons=[Button(text="Главное меню", callback_data="menu:main")],
            llm_called=settings.ai_mode == "openai",
            route=_route_payload(route),
        )

    buttons = [
        Button(
            text=f"{slot['date']} {slot['time'][:5]}",
            callback_data=build_callback("slot", "select", slot["slot_id"]),
        )
        for slot in slots
    ]
    buttons.append(Button(text="Выбрать по кнопкам", callback_data="appointment:start"))
    response = IntakeResponse(
        intent="appointment_intake",
        confidence=route.confidence,
        text=(
            f"Подойдёт направление: {route.specialty}. "
            "Выберите удобное время. Запись создаётся только после нажатия на слот."
        ),
        buttons=buttons,
        llm_called=settings.ai_mode == "openai",
        route=_route_payload(route),
        conversation_state={
            "serviceId": route.service_id,
            "doctorId": route.doctor_id,
            "visitType": route.visit_type,
        },
    )
    validate_ai_screen(response, allowed_service_ids, allowed_slot_ids)
    return response


def _route_payload(route) -> dict:
    return {
        "serviceId": route.service_id,
        "doctorId": route.doctor_id,
        "specialty": route.specialty,
        "visitType": route.visit_type,
        "durationMinutes": route.duration_minutes,
    }


if __name__ == "__main__":
    uvicorn.run("services.ai_orchestrator.main:app", host="0.0.0.0", port=8001)
