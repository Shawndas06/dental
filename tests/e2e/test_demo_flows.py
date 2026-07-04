import pytest

from services.ai_orchestrator.main import intake
from services.ai_orchestrator.main import app as ai_app
from services.bot_gateway import main as bot_main
from shared.schemas import IntakeRequest


SERVICES = [
    {
        "service_id": "svc_primary",
        "doctor_id": "doc_therapist",
        "name": "Первичная консультация",
        "category": "consultation",
        "price": 1500,
        "currency": "RUB",
        "duration_minutes": 60,
    }
]

SLOTS = [
    {
        "slot_id": "slot_doc_therapist_1_0",
        "doctor_id": "doc_therapist",
        "date": "2026-07-01",
        "time": "10:00:00",
        "duration_minutes": 60,
        "status": "available",
        "reserved_until": None,
    }
]


@pytest.mark.asyncio
async def test_text_intake_shows_real_slot_buttons(monkeypatch) -> None:
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: FakeAsyncClient())
    response = await intake(
        IntakeRequest(telegram_user_id="1001", text="Болит зуб слева уже неделю")
    )

    assert response.intent == "appointment_intake"
    assert response.buttons[0].callback_data == "slot:select:slot_doc_therapist_1_0"
    assert response.route["serviceId"] == "svc_primary"


@pytest.mark.asyncio
async def test_clinical_question_safe_refusal() -> None:
    response = await intake(IntakeRequest(telegram_user_id="1001", text="Что у меня за болезнь?"))

    assert response.intent == "clinical_question"
    assert "не могу ставить диагноз" in response.text.lower()


@pytest.mark.asyncio
async def test_unknown_service_no_hallucination() -> None:
    response = await intake(IntakeRequest(telegram_user_id="1001", text="Хочу имплантацию"))

    assert response.intent == "unknown_service"
    assert "такой услуги нет" in response.text.lower()


@pytest.mark.asyncio
async def test_button_pricing_flow_does_not_call_ai(monkeypatch) -> None:
    bot_main.AI_CALL_COUNT = 0
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: FakeAsyncClient())

    response = await bot_main.handle_update(
        {
            "callback_query": {
                "from": {"id": 1001, "username": "demo"},
                "message": {"chat": {"id": 1001}},
                "data": "pricing:list",
            }
        },
        send=False,
    )

    assert response is not None
    assert "Прайс-лист" in response.text
    assert bot_main.AI_CALL_COUNT == 0


class FakeResponse:
    def __init__(self, payload: dict | list, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict | None = None, headers: dict | None = None):
        if url.endswith("/api/patients/lookup"):
            return FakeResponse({"patient_id": "pat_demo", "is_primary": True})
        if url.endswith("/api/users/telegram/register"):
            return FakeResponse({"user_id": "usr"})
        return FakeResponse({})

    async def get(self, url: str, params: dict | None = None, headers: dict | None = None):
        if url.endswith("/api/services"):
            return FakeResponse(SERVICES)
        if url.endswith("/api/schedule/slots/available"):
            return FakeResponse(SLOTS)
        if "/api/patients/by-telegram/" in url:
            return FakeResponse(
                {
                    "patient_id": "pat_demo",
                    "telegram_user_id": "1001",
                    "name": "Demo",
                    "is_primary": True,
                }
            )
        return FakeResponse({})
