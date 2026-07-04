import uvicorn
from fastapi import FastAPI
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

settings = get_settings()
app = FastAPI(title="Dental AI Orchestrator", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ai/intake", response_model=IntakeResponse)
async def intake(payload: IntakeRequest) -> IntakeResponse:
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
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{settings.core_api_url}/api/patients/lookup",
            json={
                "telegram_user_id": payload.telegram_user_id,
                "phone": payload.phone,
            },
        )
        services_response = await client.get(f"{settings.core_api_url}/api/services")
        slots_response = await client.get(
            f"{settings.core_api_url}/api/schedule/slots/available",
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
