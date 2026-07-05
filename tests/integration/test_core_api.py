import pytest
from fastapi import HTTPException

from services.core_api.database import Base, SessionLocal, engine
from services.core_api.main import (
    approve_reschedule,
    available_slots,
    cancel_appointment,
    create_appointment,
    doctor_calendar,
    doctor_calendar_summary,
    lookup_patient,
    patient_appointments,
    publisher,
    request_reschedule_by_doctor,
)
from services.core_api.seed import seed_demo_data
from shared.patient_proof import build_patient_proof
from shared.schemas import AppointmentCreate, DoctorRescheduleRequest, PatientLookupRequest


def _patient_headers(telegram_user_id: str) -> dict[str, str]:
    return {
        "x_telegram_user_id": telegram_user_id,
        "x_patient_proof": build_patient_proof(telegram_user_id),
    }


@pytest.fixture(autouse=True)
def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
    publisher.enabled = False
    publisher.published.clear()


@pytest.mark.asyncio
async def test_create_appointment_is_idempotent_and_publishes_event() -> None:
    with SessionLocal() as db:
        patient = await lookup_patient(PatientLookupRequest(telegram_user_id="demo_patient"), db)
        slot = available_slots(db=db, doctor_id="doc_therapist")[0]

        payload = AppointmentCreate(
            patient_id=patient.patient_id,
            doctor_id="doc_therapist",
            service_id="svc_primary",
            slot_id=slot.slot_id,
            visit_type="primary_consultation",
        )
        first = await create_appointment(
            payload, db, idempotency_key="test-create", **_patient_headers("demo_patient")
        )
        second = await create_appointment(
            payload, db, idempotency_key="test-create", **_patient_headers("demo_patient")
        )

    assert first.appointment_id == second.appointment_id
    assert any(subject == "appointments.created" for subject, _ in publisher.published)
    created_event = next(event for subject, event in publisher.published if subject == "appointments.created")
    assert created_event.payload.get("chat_id") == "demo_patient"


@pytest.mark.asyncio
async def test_slot_conflict_returns_409() -> None:
    with SessionLocal() as db:
        patient = await lookup_patient(PatientLookupRequest(telegram_user_id="demo_patient"), db)
        slot = available_slots(db=db, doctor_id="doc_therapist")[0]
        payload = AppointmentCreate(
            patient_id=patient.patient_id,
            doctor_id="doc_therapist",
            service_id="svc_primary",
            slot_id=slot.slot_id,
            visit_type="primary_consultation",
        )

        await create_appointment(payload, db, idempotency_key="a", **_patient_headers("demo_patient"))
        with pytest.raises(Exception) as exc:
            await create_appointment(payload, db, idempotency_key="b", **_patient_headers("demo_patient"))

    assert getattr(exc.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_doctor_reschedule_requires_patient_approval() -> None:
    with SessionLocal() as db:
        patient = await lookup_patient(PatientLookupRequest(telegram_user_id="demo_patient"), db)
        slots = available_slots(db=db, doctor_id="doc_therapist", limit=2)
        created = await create_appointment(
            AppointmentCreate(
                patient_id=patient.patient_id,
                doctor_id="doc_therapist",
                service_id="svc_primary",
                slot_id=slots[0].slot_id,
                visit_type="primary_consultation",
            ),
            db,
            idempotency_key="create-for-reschedule",
            **_patient_headers("demo_patient"),
        )

        request = await request_reschedule_by_doctor(
            created.appointment_id,
            DoctorRescheduleRequest(doctor_id="doc_therapist", proposed_slot_id=slots[1].slot_id),
            db,
            idempotency_key="doctor-request",
            x_telegram_user_id="987654321",
            x_role="doctor",
        )
        approved = await approve_reschedule(
            request.approval_request_id,
            db,
            idempotency_key="approve-request",
            **_patient_headers("demo_patient"),
        )

    assert request.status == "waiting_patient_approval"
    assert approved.slot_id == slots[1].slot_id
    assert approved.status == "rescheduled"


@pytest.mark.asyncio
async def test_patient_lookup_creates_primary_patient() -> None:
    with SessionLocal() as db:
        response = await lookup_patient(PatientLookupRequest(telegram_user_id="new-user"), db)

    assert response.is_primary is True


def test_patient_appointments_requires_owner() -> None:
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            patient_appointments("pat_demo", db, **_patient_headers("999999999"))
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_cancel_appointment_requires_owner() -> None:
    with SessionLocal() as db:
        patient = await lookup_patient(PatientLookupRequest(telegram_user_id="demo_patient"), db)
        slot = available_slots(db=db, doctor_id="doc_therapist")[0]
        created = await create_appointment(
            AppointmentCreate(
                patient_id=patient.patient_id,
                doctor_id="doc_therapist",
                service_id="svc_primary",
                slot_id=slot.slot_id,
                visit_type="primary_consultation",
            ),
            db,
            idempotency_key="cancel-owner-test",
            **_patient_headers("demo_patient"),
        )
        with pytest.raises(HTTPException) as exc:
            await cancel_appointment(
                created.appointment_id,
                db,
                idempotency_key="cancel-other",
                **_patient_headers("999999999"),
            )
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_appointment_requires_patient_owner() -> None:
    with SessionLocal() as db:
        patient = await lookup_patient(PatientLookupRequest(telegram_user_id="demo_patient"), db)
        slot = available_slots(db=db, doctor_id="doc_therapist")[0]
        payload = AppointmentCreate(
            patient_id=patient.patient_id,
            doctor_id="doc_therapist",
            service_id="svc_primary",
            slot_id=slot.slot_id,
            visit_type="primary_consultation",
        )
        with pytest.raises(HTTPException) as exc:
            await create_appointment(
                payload, db, idempotency_key="other-user", **_patient_headers("999999999")
            )
        assert exc.value.status_code == 403


def test_doctor_calendar_summary_is_public() -> None:
    with SessionLocal() as db:
        result = doctor_calendar_summary("doc_therapist", db)
    assert isinstance(result, list)


def test_doctor_calendar_full_requires_auth() -> None:
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            doctor_calendar("doc_therapist", db, x_telegram_user_id="999999999", x_role="doctor")
        assert exc.value.status_code == 403
