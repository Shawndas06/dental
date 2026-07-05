import pytest

from shared.conversation_state import clear_state_cache, get_state, merge_state, save_state
from shared.patient_proof import build_patient_proof, verify_patient_proof


@pytest.fixture(autouse=True)
def reset_state(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-internal-token")
    from shared.config import get_settings

    get_settings.cache_clear()
    clear_state_cache()
    yield
    clear_state_cache()
    get_settings.cache_clear()


def test_merge_state_persists_service_id() -> None:
    merge_state("1001", {"serviceId": "svc_hygiene"})
    assert get_state("1001")["serviceId"] == "svc_hygiene"


def test_save_state_overwrites() -> None:
    save_state("1001", {"doctorId": "doc_therapist"})
    save_state("1001", {"serviceId": "svc_primary"})
    assert get_state("1001") == {"serviceId": "svc_primary"}


def test_patient_proof_roundtrip() -> None:
    proof = build_patient_proof("demo_patient")
    verify_patient_proof("demo_patient", proof)


def test_patient_proof_rejects_mismatch() -> None:
    from fastapi import HTTPException

    proof = build_patient_proof("demo_patient")
    with pytest.raises(HTTPException) as exc:
        verify_patient_proof("other_user", proof)
    assert exc.value.status_code == 403
