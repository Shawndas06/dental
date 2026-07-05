import time

from services.admin.main import LOGIN_SESSIONS, SESSION_TTL_SECONDS, _is_authenticated


class DummyRequest:
    def __init__(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies


def test_admin_session_expires(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    from shared.config import get_settings

    get_settings.cache_clear()
    LOGIN_SESSIONS.clear()
    LOGIN_SESSIONS["expired"] = time.monotonic() - 1
    LOGIN_SESSIONS["active"] = time.monotonic() + SESSION_TTL_SECONDS

    assert _is_authenticated(DummyRequest({"admin_session": "expired"})) is False
    assert _is_authenticated(DummyRequest({"admin_session": "active"})) is True
    get_settings.cache_clear()
