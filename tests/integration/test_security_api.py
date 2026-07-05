import httpx
import pytest
from fastapi import HTTPException

from services.core_api.database import Base, SessionLocal, engine
from services.core_api.main import app
from services.core_api.seed import seed_demo_data
from shared.patient_proof import build_patient_proof


@pytest.fixture(autouse=True)
def reset_database(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-internal-token")
    from shared.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
    yield
    get_settings.cache_clear()


def _auth_headers(telegram_user_id: str | None = None) -> dict[str, str]:
    headers = {"X-Service-Token": "test-internal-token"}
    if telegram_user_id:
        headers["X-Telegram-User-Id"] = telegram_user_id
        headers["X-Patient-Proof"] = build_patient_proof(telegram_user_id)
    return headers


def test_service_token_required() -> None:
    from shared.security import verify_service_token

    with pytest.raises(HTTPException) as exc:
        verify_service_token(None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_public_api_rejects_missing_service_token() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/services")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_public_api_accepts_valid_service_token() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/services",
            headers={"X-Service-Token": "test-internal-token"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_appointment_rejects_wrong_patient_header() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        slots = await client.get(
            "/api/schedule/slots/available",
            headers={"X-Service-Token": "test-internal-token"},
            params={"doctor_id": "doc_therapist", "limit": 1},
        )
        slot_id = slots.json()[0]["slot_id"]
        response = await client.post(
            "/api/appointments",
            headers={
                **_auth_headers("attacker"),
            },
            json={
                "patient_id": "pat_demo",
                "doctor_id": "doc_therapist",
                "service_id": "svc_primary",
                "slot_id": slot_id,
                "visit_type": "primary_consultation",
            },
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_doctor_appointments_rejects_role_spoof() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/appointments/doctor/doc_therapist",
            headers={
                "X-Service-Token": "test-internal-token",
                "X-Telegram-User-Id": "999999999",
                "X-Role": "doctor",
            },
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_patient_lookup_requires_proof() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        missing_proof = await client.get(
            "/api/patients/by-telegram/demo_patient",
            headers={"X-Service-Token": "test-internal-token", "X-Telegram-User-Id": "demo_patient"},
        )
        with_proof = await client.get(
            "/api/patients/by-telegram/demo_patient",
            headers=_auth_headers("demo_patient"),
        )
    assert missing_proof.status_code == 403
    assert with_proof.status_code == 200


@pytest.mark.asyncio
async def test_removed_public_audit_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/audit",
            headers={"X-Service-Token": "test-internal-token"},
        )
    assert response.status_code == 404
