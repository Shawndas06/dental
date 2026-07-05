import logging

from shared.config import get_settings

logger = logging.getLogger(__name__)

WEAK_SECRETS = {
    "",
    "change-me",
    "change-me-admin-token",
    "change-me-internal-token",
    "change-me-to-random-value",
    "dental",
    "dental-local-dev",
}


def warn_insecure_defaults() -> None:
    settings = get_settings()
    issues: list[str] = []
    if settings.admin_token in WEAK_SECRETS:
        issues.append("ADMIN_TOKEN uses a default or empty value")
    if settings.internal_service_token in WEAK_SECRETS:
        issues.append("INTERNAL_SERVICE_TOKEN uses a default or empty value")
    if settings.telegram_webhook_secret in WEAK_SECRETS and settings.telegram_mode.lower() == "webhook":
        issues.append("TELEGRAM_WEBHOOK_SECRET uses a default or empty value")
    for issue in issues:
        logger.warning("Security: %s", issue)
