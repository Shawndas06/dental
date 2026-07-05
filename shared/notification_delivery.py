import logging

from shared.config import get_settings
from shared.conversation_state import get_state, save_state
from shared.telegram_client import post_telegram_api

logger = logging.getLogger(__name__)

DEFAULT_NOTIFY_TEXT = (
    "Демо стоматология: MVP запущен и протестирован. "
    "Это одно тестовое уведомление на сегодня."
)


def _notify_state_key(username: str) -> str:
    return f"notify:sent:{username.lower().lstrip('@')}"


def already_notified(username: str) -> bool:
    key = _notify_state_key(username)
    state = get_state(key)
    return bool(state.get("sent"))


def mark_notified(username: str) -> None:
    save_state(_notify_state_key(username), {"sent": True})


async def send_target_notification(chat_id: str, username: str | None, text: str | None = None) -> bool:
    settings = get_settings()
    target = settings.notify_telegram_username.strip().lstrip("@").lower()
    if not target or not username or username.lower() != target:
        return False
    if already_notified(target):
        return False
    if not settings.telegram_bot_token:
        return False
    message = text or DEFAULT_NOTIFY_TEXT
    url = f"{settings.telegram_api_base.rstrip('/')}/bot{settings.telegram_bot_token}/sendMessage"
    try:
        await post_telegram_api(url, json={"chat_id": chat_id, "text": message}, timeout=15)
        mark_notified(target)
        logger.info("Sent target notification to @%s chat_id=%s", target, chat_id)
        return True
    except Exception as exc:
        logger.warning("Failed to send target notification to @%s: %s", target, exc)
        return False
