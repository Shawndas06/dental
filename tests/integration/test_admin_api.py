import pytest

from services.core_api.admin import admin_dashboard, admin_demo_reset, verify_admin_token
from services.core_api.database import Base, SessionLocal, engine
from services.core_api.demo_reset import reset_demo_db
from services.core_api.seed import seed_demo_data
from fastapi import HTTPException


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


def test_admin_dashboard_ok() -> None:
    with SessionLocal() as db:
        data = admin_dashboard(None, db)
    assert data["doctors"] >= 1
    assert data["services"] >= 1
    assert "slotsAvailable" in data


def test_admin_demo_reset() -> None:
    with SessionLocal() as db:
        result = reset_demo_db(db)
    assert result["slotsReset"] > 0
