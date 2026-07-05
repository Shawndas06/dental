import pytest
from fastapi import HTTPException

from shared.config import get_settings
from shared.security import SlidingWindowRateLimiter, mask_phone, require_permission, verify_debug_access, verify_service_token


def test_patient_cannot_request_doctor_reschedule() -> None:
    with pytest.raises(HTTPException) as exc:
        require_permission("patient", "reschedule:request:doctor")

    assert exc.value.status_code == 403


def test_doctor_can_read_doctor_calendar() -> None:
    require_permission("doctor", "calendar:read:doctor")


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)

    assert limiter.allow("chat-1") is True
    assert limiter.allow("chat-1") is True
    assert limiter.allow("chat-1") is False


def test_mask_phone() -> None:
    assert mask_phone("+79990000000") == "+7***0000"


def test_debug_access_requires_token(monkeypatch) -> None:
    monkeypatch.setenv("DEBUG_API_ENABLED", "true")
    monkeypatch.setenv("DEBUG_API_TOKEN", "secret-debug")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        verify_debug_access(None)
    assert exc.value.status_code == 401
    get_settings.cache_clear()


def test_debug_access_disabled_returns_404(monkeypatch) -> None:
    monkeypatch.setenv("DEBUG_API_ENABLED", "false")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        verify_debug_access("anything")
    assert exc.value.status_code == 404
    get_settings.cache_clear()


def test_service_token_rejects_invalid() -> None:
    with pytest.raises(HTTPException) as exc:
        verify_service_token("wrong")
    assert exc.value.status_code == 401
