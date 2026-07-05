import httpx
import pytest


@pytest.fixture(autouse=True)
def configure_token(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-internal-token")
    from shared.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_crm_lookup_requires_service_token() -> None:
    from services.crm_mock.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.post(
            "/crm/patients/lookup",
            json={"telegram_user_id": "demo"},
        )
        authorized = await client.post(
            "/crm/patients/lookup",
            headers={"X-Service-Token": "test-internal-token"},
            json={"telegram_user_id": "demo"},
        )
    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
