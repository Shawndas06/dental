import hashlib
import hmac
import re
import time
from collections import defaultdict, deque
from enum import StrEnum

from fastapi import Header, HTTPException, Request, status


class Role(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    STAFF = "staff"
    ADMIN = "admin"


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.PATIENT: {
        "appointment:create",
        "appointment:list:self",
        "appointment:reschedule:self",
        "appointment:cancel:self",
        "reschedule:approve:self",
        "pricing:read",
        "calendar:read:self",
    },
    Role.DOCTOR: {
        "appointment:list:doctor",
        "reschedule:request:doctor",
        "pricing:read",
        "calendar:read:doctor",
    },
    Role.STAFF: {
        "appointment:read:any",
        "calendar:read:doctor",
        "crm:errors:read",
        "pricing:read",
    },
    Role.ADMIN: {"*"},
}


class SlidingWindowRateLimiter:
    def __init__(self, limit: int = 60, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


def require_permission(role: str, permission: str) -> None:
    parsed = Role(role)
    permissions = ROLE_PERMISSIONS[parsed]
    if "*" not in permissions and permission not in permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def verify_webhook_secret(
    expected_secret: str,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> None:
    if not expected_secret:
        return
    provided = x_telegram_bot_api_secret_token or ""
    if not hmac.compare_digest(provided, expected_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


async def rate_limit_request(request: Request, limiter: SlidingWindowRateLimiter) -> None:
    body = await request.json()
    chat_id = (
        body.get("message", {}).get("chat", {}).get("id")
        or body.get("callback_query", {}).get("message", {}).get("chat", {}).get("id")
        or request.client.host
    )
    if not limiter.allow(str(chat_id)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 5:
        return "***"
    return f"+{digits[:1]}***{digits[-4:]}"


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
