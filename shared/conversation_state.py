import json
from typing import Any

from shared.config import get_settings

_memory: dict[str, dict[str, Any]] = {}
_redis_client = None


def _redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        import redis

        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_client = None
        return None


def _key(telegram_user_id: str) -> str:
    return f"bot:state:{telegram_user_id}"


def get_state(telegram_user_id: str) -> dict[str, Any]:
    client = _redis()
    if client:
        raw = client.get(_key(telegram_user_id))
        if raw:
            return json.loads(raw)
        return {}
    return dict(_memory.get(telegram_user_id, {}))


def save_state(telegram_user_id: str, state: dict[str, Any]) -> None:
    client = _redis()
    if client:
        client.setex(_key(telegram_user_id), 86400, json.dumps(state))
        return
    _memory[telegram_user_id] = dict(state)


def merge_state(telegram_user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    merged = {**get_state(telegram_user_id), **patch}
    save_state(telegram_user_id, merged)
    return merged


def clear_state_cache() -> None:
    global _redis_client
    _memory.clear()
    _redis_client = None
