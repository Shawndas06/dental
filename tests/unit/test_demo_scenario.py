import pytest

from services.core_api.demo_scenario import DEMO_TELEGRAM_USER_ID, _debug_headers, _patient_headers


def test_demo_helpers() -> None:
    assert _patient_headers()["X-Telegram-User-Id"] == DEMO_TELEGRAM_USER_ID
    assert "X-Debug-Token" in _debug_headers()
