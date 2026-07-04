import pytest

from services.core_api.database import Base, SessionLocal, engine
from services.core_api.main import (
    approve_reschedule,
    available_slots,
    create_appointment,
    lookup_patient,
    publisher,
    request_reschedule_by_doctor,
)
from services.core_api.seed import seed_demo_data
from shared.schemas import AppointmentCreate, DoctorRescheduleRequest, PatientLookupRequest


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
        first = await create_appointment(payload, None, db, idempotency_key="test-create")
        second = await create_appointment(payload, None, db, idempotency_key="test-create")

    assert first.appointment_id == second.appointment_id
    assert any(subject == "appointments.created" for subject, _ in publisher.published)


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

        await create_appointment(payload, None, db, idempotency_key="a")
        with pytest.raises(Exception) as exc:
            await create_appointment(payload, None, db, idempotency_key="b")

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
            None,
            db,
            idempotency_key="create-for-reschedule",
        )

        request = await request_reschedule_by_doctor(
            created.appointment_id,
            DoctorRescheduleRequest(doctor_id="doc_therapist", proposed_slot_id=slots[1].slot_id),
            db,
            idempotency_key="doctor-request",
            x_role="doctor",
        )
        approved = await approve_reschedule(
            request.approval_request_id,
            db,
            idempotency_key="approve-request",
        )

    assert request.status == "waiting_patient_approval"
    assert approved.slot_id == slots[1].slot_id
    assert approved.status == "rescheduled"


@pytest.mark.asyncio
async def test_patient_lookup_creates_primary_patient() -> None:
    with SessionLocal() as db:
        response = await lookup_patient(PatientLookupRequest(telegram_user_id="new-user"), db)

    assert response.is_primary is True
