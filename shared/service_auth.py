from shared.config import get_settings
from shared.patient_proof import build_patient_proof


def internal_service_headers(
    *,
    telegram_user_id: str | None = None,
    **extra: str,
) -> dict[str, str]:
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.internal_service_token:
        headers["X-Service-Token"] = settings.internal_service_token
    if telegram_user_id:
        headers["X-Telegram-User-Id"] = telegram_user_id
        proof = build_patient_proof(telegram_user_id)
        if proof:
            headers["X-Patient-Proof"] = proof
    headers.update(extra)
    return headers
