import hashlib
import hmac
import time

from fastapi import HTTPException, status

from shared.config import get_settings
from shared.security import safe_compare_digest

PROOF_TTL_SECONDS = 300


def build_patient_proof(telegram_user_id: str, timestamp: int | None = None) -> str:
    settings = get_settings()
    if not settings.internal_service_token:
        return ""
    ts = timestamp or int(time.time())
    payload = f"{telegram_user_id}:{ts}"
    digest = hmac.new(
        settings.internal_service_token.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{ts}:{digest}"


def verify_patient_proof(telegram_user_id: str, proof: str | None) -> None:
    if not isinstance(proof, str):
        proof = None
    if not proof or ":" not in proof:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid patient proof")
    ts_raw, provided_sig = proof.split(":", 1)
    try:
        ts = int(ts_raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid patient proof") from exc
    if abs(int(time.time()) - ts) > PROOF_TTL_SECONDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient proof expired")
    expected = build_patient_proof(telegram_user_id, timestamp=ts).split(":", 1)[1]
    if not safe_compare_digest(provided_sig, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid patient proof")
