import httpx
import pytest
from fastapi import HTTPException

from services.core_api.admin import verify_admin_token
from services.core_api.database import Base, SessionLocal, engine
from services.core_api.main import app
from services.core_api.seed import seed_demo_data


@pytest.fixture(autouse=True)
def reset_database(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    from shared.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
    yield
    get_settings.cache_clear()


def test_admin_token_required() -> None:
    with pytest.raises(HTTPException) as exc:
        verify_admin_token(None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_admin_dashboard_http() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/api/admin/dashboard")
        assert unauthorized.status_code == 401

        response = await client.get(
            "/api/admin/dashboard",
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["doctors"] >= 1
        assert data["services"] >= 1
        assert "slotsAvailable" in data


@pytest.mark.asyncio
async def test_admin_demo_reset_http() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/admin/demo/reset",
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert response.status_code == 200
        assert response.json()["slotsReset"] > 0
