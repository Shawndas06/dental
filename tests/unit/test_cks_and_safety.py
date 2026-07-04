import pytest

from services.ai_orchestrator.cks import classify_text, route_text
from services.ai_orchestrator.safety import safe_refusal, validate_ai_screen
from shared.schemas import Button, IntakeResponse


def test_pain_routes_to_primary_therapist() -> None:
    route = route_text("Болит зуб слева уже неделю")

    assert route.doctor_id == "doc_therapist"
    assert route.service_id == "svc_primary"
    assert route.visit_type == "primary_consultation"
    assert route.confidence >= 0.8


def test_clinical_question_is_refused() -> None:
    assert classify_text("Что у меня за болезнь?") == "clinical_question"
    response = safe_refusal()

    assert response.intent == "clinical_question"
    assert "не могу ставить диагноз" in response.text.lower()
    assert response.llm_called is False


def test_validator_rejects_unknown_slot() -> None:
    response = IntakeResponse(
        intent="appointment_intake",
        confidence=0.9,
        text="Выберите слот.",
        route={"serviceId": "svc_primary"},
        buttons=[Button(text="10:00", callback_data="slot:select:slot_missing")],
    )

    with pytest.raises(ValueError):
        validate_ai_screen(response, {"svc_primary"}, {"slot_existing"})


def test_validator_rejects_clinical_advice() -> None:
    response = IntakeResponse(
        intent="appointment_intake",
        confidence=0.9,
        text="Это точно диагноз, лечите таблетками.",
        route={"serviceId": "svc_primary"},
    )

    with pytest.raises(ValueError):
        validate_ai_screen(response, {"svc_primary"}, set())
