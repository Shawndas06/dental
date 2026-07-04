import pytest
from fastapi import HTTPException

from shared.security import SlidingWindowRateLimiter, mask_phone, require_permission


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
