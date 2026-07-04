import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core_api.database import create_schema, get_db
from services.core_api.models import (
    Appointment,
    AuditEvent,
    ClinicService,
    Doctor,
    IdempotencyRecord,
    Notification,
    Patient,
    RescheduleRequest,
    Slot,
    User,
)
from services.core_api.admin import router as admin_router
from services.core_api.seed import clinic_profile, seed_demo_data
from shared.config import get_settings
from shared.events import event_for
from shared.nats import EventPublisher
from shared.schemas import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatus,
    DoctorRead,
    DoctorRescheduleRequest,
    NotificationCreate,
    PatientLookupRequest,
    PatientQuickRegisterRequest,
    PatientRead,
    PatientRescheduleRequest,
    RescheduleRead,
    RescheduleStatus,
    ServiceRead,
    SlotRead,
    UserCreate,
    UserRead,
)
from shared.security import require_permission

settings = get_settings()
app = FastAPI(title="Dental Bot Core API", version="0.1.0")
app.include_router(admin_router)
publisher = EventPublisher(settings.nats_url)


Db = Annotated[Session, Depends(get_db)]


@app.on_event("startup")
async def startup() -> None:
    create_schema()
    with next(get_db()) as db:
        seed_demo_data(db)
    if not settings.database_url.startswith("sqlite"):
        asyncio.create_task(publisher.connect())


@app.on_event("shutdown")
async def shutdown() -> None:
    await publisher.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/debug/events")
def debug_events() -> list[dict]:
    return [
        {"subject": subject, "event": event.model_dump(mode="json")}
        for subject, event in publisher.published
    ]


@app.post("/api/users/telegram/register", response_model=UserRead)
def register_user(payload: UserCreate, db: Db) -> UserRead:
    existing = db.scalar(select(User).where(User.telegram_user_id == payload.telegram_user_id))
    if existing:
        existing.chat_id = payload.chat_id
        existing.username = payload.username
        existing.phone = payload.phone
        existing.role = payload.role
        user = existing
    else:
        user = User(**payload.model_dump())
        db.add(user)
    db.commit()
    db.refresh(user)
    return _user_read(user)


@app.post("/api/patients/lookup", response_model=PatientRead)
async def lookup_patient(payload: PatientLookupRequest, db: Db) -> PatientRead:
    patient = db.scalar(select(Patient).where(Patient.telegram_user_id == payload.telegram_user_id))
    if patient:
        return _patient_read(patient)

    crm_data = await _lookup_crm(payload)
    patient = Patient(
        crm_patient_id=crm_data.get("crmPatientId"),
        telegram_user_id=payload.telegram_user_id,
        name=crm_data.get("name") or "Пациент",
        phone=payload.phone,
        is_primary=not bool(crm_data.get("exists")),
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return _patient_read(patient)


@app.get("/api/patients/by-telegram/{telegram_user_id}", response_model=PatientRead)
def get_patient_by_telegram(telegram_user_id: str, db: Db) -> PatientRead:
    patient = db.scalar(select(Patient).where(Patient.telegram_user_id == telegram_user_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return _patient_read(patient)


@app.post("/api/patients/quick-register", response_model=PatientRead)
async def quick_register_patient(payload: PatientQuickRegisterRequest, db: Db) -> PatientRead:
    user = db.scalar(select(User).where(User.telegram_user_id == payload.telegram_user_id))
    if user:
        user.chat_id = payload.chat_id
        user.username = payload.username
        if payload.phone:
            user.phone = payload.phone
    else:
        user = User(
            telegram_user_id=payload.telegram_user_id,
            chat_id=payload.chat_id,
            username=payload.username,
            phone=payload.phone,
            role="patient",
        )
        db.add(user)

    patient = db.scalar(select(Patient).where(Patient.telegram_user_id == payload.telegram_user_id))
    crm_data = await _lookup_crm(PatientLookupRequest(telegram_user_id=payload.telegram_user_id, phone=payload.phone))
    if patient:
        patient.name = payload.name.strip() or patient.name
        if payload.phone:
            patient.phone = payload.phone
        if crm_data.get("crmPatientId"):
            patient.crm_patient_id = crm_data["crmPatientId"]
        patient.is_primary = not bool(crm_data.get("exists"))
    else:
        patient = Patient(
            crm_patient_id=crm_data.get("crmPatientId"),
            telegram_user_id=payload.telegram_user_id,
            name=payload.name.strip() or crm_data.get("name") or "Пациент",
            phone=payload.phone,
            is_primary=not bool(crm_data.get("exists")),
        )
        db.add(patient)
    db.commit()
    db.refresh(patient)
    return _patient_read(patient)


@app.get("/api/doctors", response_model=list[DoctorRead])
def list_doctors(db: Db) -> list[DoctorRead]:
    return [_doctor_read(item) for item in db.scalars(select(Doctor)).all()]


@app.get("/api/services", response_model=list[ServiceRead])
def list_services(
    db: Db,
    doctor_id: str | None = None,
    category: str | None = None,
) -> list[ServiceRead]:
    query = select(ClinicService)
    if doctor_id:
        query = query.where(ClinicService.doctor_id == doctor_id)
    if category:
        query = query.where(ClinicService.category == category)
    return [_service_read(item) for item in db.scalars(query).all()]


@app.get("/api/pricing/doctor/{doctor_id}", response_model=list[ServiceRead])
def doctor_pricing(doctor_id: str, db: Db) -> list[ServiceRead]:
    return list_services(db=db, doctor_id=doctor_id)


@app.get("/api/clinic-profile")
def get_clinic_profile() -> dict:
    return clinic_profile()


@app.get("/api/clinic-profile/service/{service_name}/available")
def check_service_available(service_name: str, db: Db) -> dict[str, bool | str | None]:
    service = db.scalar(
        select(ClinicService).where(ClinicService.name.ilike(f"%{service_name.strip()}%"))
    )
    return {"available": bool(service), "serviceId": service.service_id if service else None}


@app.get("/api/schedule/slots/available", response_model=list[SlotRead])
def available_slots(
    db: Db,
    doctor_id: str | None = None,
    service_id: str | None = None,
    limit: int = 6,
) -> list[SlotRead]:
    limit = max(1, min(int(limit), 20))
    query = select(Slot).where(Slot.status == "available")
    if doctor_id:
        query = query.where(Slot.doctor_id == doctor_id)
    elif service_id:
        service = db.get(ClinicService, service_id)
        if service:
            query = query.where(Slot.doctor_id == service.doctor_id)
    query = query.order_by(Slot.date, Slot.time).limit(limit)
    return [_slot_read(item) for item in db.scalars(query).all()]


@app.get("/api/calendar/doctor/{doctor_id}", response_model=list[AppointmentRead])
def doctor_calendar(doctor_id: str, db: Db, x_role: str = Header(default="doctor")) -> list[AppointmentRead]:
    require_permission(x_role, "calendar:read:doctor")
    appointments = db.scalars(select(Appointment).where(Appointment.doctor_id == doctor_id)).all()
    return [_appointment_read(item) for item in appointments]


@app.get("/api/calendar/patient/{patient_id}", response_model=list[AppointmentRead])
def patient_calendar(patient_id: str, db: Db) -> list[AppointmentRead]:
    appointments = db.scalars(select(Appointment).where(Appointment.patient_id == patient_id)).all()
    return [_appointment_read(item) for item in appointments]


@app.post("/api/appointments", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    request: Request,
    db: Db,
    idempotency_key: str = Header(default=""),
) -> AppointmentRead:
    key = idempotency_key or f"appointment-create:{payload.patient_id}:{payload.slot_id}"
    cached = db.get(IdempotencyRecord, key)
    if cached:
        return AppointmentRead.model_validate(cached.response)

    slot = _available_slot_or_409(db, payload.slot_id)
    service = db.get(ClinicService, payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if service.doctor_id != payload.doctor_id:
        raise HTTPException(status_code=400, detail="Doctor does not provide selected service")
    if not db.get(Patient, payload.patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")

    slot.status = "booked"
    appointment = Appointment(
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
        service_id=payload.service_id,
        slot_id=payload.slot_id,
        visit_type=payload.visit_type,
        status=AppointmentStatus.CONFIRMED,
        date=slot.date,
        time=slot.time,
    )
    db.add(appointment)
    db.add(AuditEvent(event_type="appointments.created", actor_id=payload.patient_id, payload=payload.model_dump()))
    db.commit()
    db.refresh(appointment)

    response = _appointment_read(appointment)
    db.add(IdempotencyRecord(key=key, response=response.model_dump(mode="json")))
    db.commit()
    await _publish("appointments.created", key, response.model_dump(mode="json"))
    await _publish("crm.appointment.sync_requested", f"crm-sync:{appointment.appointment_id}", response.model_dump(mode="json"))
    return response


@app.get("/api/appointments/patient/{patient_id}", response_model=list[AppointmentRead])
def patient_appointments(patient_id: str, db: Db) -> list[AppointmentRead]:
    return [_appointment_read(item) for item in db.scalars(select(Appointment).where(Appointment.patient_id == patient_id)).all()]


@app.get("/api/appointments/doctor/{doctor_id}", response_model=list[AppointmentRead])
def doctor_appointments(doctor_id: str, db: Db, x_role: str = Header(default="doctor")) -> list[AppointmentRead]:
    require_permission(x_role, "appointment:list:doctor")
    return [_appointment_read(item) for item in db.scalars(select(Appointment).where(Appointment.doctor_id == doctor_id)).all()]


@app.post("/api/appointments/{appointment_id}/cancel", response_model=AppointmentRead)
async def cancel_appointment(appointment_id: str, db: Db, idempotency_key: str = Header(default="")) -> AppointmentRead:
    appointment = _appointment_or_404(db, appointment_id)
    key = idempotency_key or f"appointment-cancel:{appointment_id}"
    cached = db.get(IdempotencyRecord, key)
    if cached:
        return AppointmentRead.model_validate(cached.response)
    appointment.status = AppointmentStatus.CANCELLED
    slot = db.get(Slot, appointment.slot_id)
    if slot:
        slot.status = "available"
    db.add(AuditEvent(event_type="appointments.cancelled", actor_id=appointment.patient_id, payload={"appointmentId": appointment_id}))
    db.commit()
    response = _appointment_read(appointment)
    db.add(IdempotencyRecord(key=key, response=response.model_dump(mode="json")))
    db.commit()
    await _publish("appointments.cancelled", key, response.model_dump(mode="json"))
    return response


@app.post("/api/appointments/{appointment_id}/reschedule/by-patient", response_model=AppointmentRead)
async def reschedule_by_patient(
    appointment_id: str,
    payload: PatientRescheduleRequest,
    db: Db,
    idempotency_key: str = Header(default=""),
) -> AppointmentRead:
    appointment = _appointment_or_404(db, appointment_id)
    key = idempotency_key or f"reschedule-patient:{appointment_id}:{payload.new_slot_id}"
    cached = db.get(IdempotencyRecord, key)
    if cached:
        return AppointmentRead.model_validate(cached.response)
    new_slot = _available_slot_or_409(db, payload.new_slot_id)
    old_slot = db.get(Slot, appointment.slot_id)
    if old_slot:
        old_slot.status = "available"
    new_slot.status = "booked"
    appointment.slot_id = new_slot.slot_id
    appointment.doctor_id = new_slot.doctor_id
    appointment.date = new_slot.date
    appointment.time = new_slot.time
    appointment.status = AppointmentStatus.RESCHEDULED
    db.add(AuditEvent(event_type="appointments.rescheduled.by_patient", actor_id=appointment.patient_id, payload={"appointmentId": appointment_id}))
    db.commit()
    response = _appointment_read(appointment)
    db.add(IdempotencyRecord(key=key, response=response.model_dump(mode="json")))
    db.commit()
    await _publish("appointments.rescheduled.by_patient", key, response.model_dump(mode="json"))
    return response


@app.post("/api/appointments/{appointment_id}/reschedule/request-by-doctor", response_model=RescheduleRead)
async def request_reschedule_by_doctor(
    appointment_id: str,
    payload: DoctorRescheduleRequest,
    db: Db,
    idempotency_key: str = Header(default=""),
    x_role: str = Header(default="doctor"),
) -> RescheduleRead:
    require_permission(x_role, "reschedule:request:doctor")
    appointment = _appointment_or_404(db, appointment_id)
    if appointment.doctor_id != payload.doctor_id:
        raise HTTPException(status_code=403, detail="Doctor can reschedule only own appointments")
    proposed_slot = _available_slot_or_409(db, payload.proposed_slot_id)
    key = idempotency_key or f"reschedule-request:{appointment_id}:{payload.proposed_slot_id}"
    cached = db.get(IdempotencyRecord, key)
    if cached:
        return RescheduleRead.model_validate(cached.response)
    proposed_slot.status = "reserved"
    request = RescheduleRequest(
        appointment_id=appointment_id,
        requested_by="doctor",
        old_slot_id=appointment.slot_id,
        proposed_slot_id=payload.proposed_slot_id,
        status=RescheduleStatus.WAITING_PATIENT_APPROVAL,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    appointment.status = AppointmentStatus.WAITING_PATIENT_APPROVAL
    db.add(request)
    db.add(AuditEvent(event_type="appointments.reschedule.requested_by_doctor", actor_id=payload.doctor_id, payload={"appointmentId": appointment_id}))
    db.commit()
    db.refresh(request)
    response = _reschedule_read(request)
    db.add(IdempotencyRecord(key=key, response=response.model_dump(mode="json")))
    db.commit()
    await _publish("appointments.reschedule.requested_by_doctor", key, response.model_dump(mode="json"))
    return response


@app.post("/api/reschedule/{approval_request_id}/approve", response_model=AppointmentRead)
async def approve_reschedule(approval_request_id: str, db: Db, idempotency_key: str = Header(default="")) -> AppointmentRead:
    request = _reschedule_or_404(db, approval_request_id)
    key = idempotency_key or f"reschedule-approve:{approval_request_id}"
    cached = db.get(IdempotencyRecord, key)
    if cached:
        return AppointmentRead.model_validate(cached.response)
    appointment = _appointment_or_404(db, request.appointment_id)
    new_slot = db.get(Slot, request.proposed_slot_id)
    old_slot = db.get(Slot, request.old_slot_id)
    if not new_slot or new_slot.status not in {"available", "reserved"}:
        raise HTTPException(status_code=409, detail="Proposed slot is not available")
    if old_slot:
        old_slot.status = "available"
    new_slot.status = "booked"
    appointment.slot_id = new_slot.slot_id
    appointment.doctor_id = new_slot.doctor_id
    appointment.date = new_slot.date
    appointment.time = new_slot.time
    appointment.status = AppointmentStatus.RESCHEDULED
    request.status = RescheduleStatus.APPROVED
    db.add(AuditEvent(event_type="appointments.reschedule.approved_by_patient", actor_id=appointment.patient_id, payload={"approvalRequestId": approval_request_id}))
    db.commit()
    response = _appointment_read(appointment)
    db.add(IdempotencyRecord(key=key, response=response.model_dump(mode="json")))
    db.commit()
    await _publish("appointments.reschedule.approved_by_patient", key, response.model_dump(mode="json"))
    return response


@app.post("/api/reschedule/{approval_request_id}/reject", response_model=RescheduleRead)
async def reject_reschedule(approval_request_id: str, db: Db, idempotency_key: str = Header(default="")) -> RescheduleRead:
    request = _reschedule_or_404(db, approval_request_id)
    key = idempotency_key or f"reschedule-reject:{approval_request_id}"
    cached = db.get(IdempotencyRecord, key)
    if cached:
        return RescheduleRead.model_validate(cached.response)
    request.status = RescheduleStatus.REJECTED
    proposed_slot = db.get(Slot, request.proposed_slot_id)
    if proposed_slot and proposed_slot.status == "reserved":
        proposed_slot.status = "available"
    appointment = _appointment_or_404(db, request.appointment_id)
    appointment.status = AppointmentStatus.CONFIRMED
    db.add(AuditEvent(event_type="appointments.reschedule.rejected_by_patient", actor_id=appointment.patient_id, payload={"approvalRequestId": approval_request_id}))
    db.commit()
    response = _reschedule_read(request)
    db.add(IdempotencyRecord(key=key, response=response.model_dump(mode="json")))
    db.commit()
    await _publish("appointments.reschedule.rejected_by_patient", key, response.model_dump(mode="json"))
    return response


@app.get("/api/reminders/due", response_model=list[AppointmentRead])
def due_reminders(db: Db) -> list[AppointmentRead]:
    target = datetime.now(UTC) + timedelta(hours=24)
    start = target - timedelta(minutes=30)
    end = target + timedelta(minutes=30)
    appointments = db.scalars(
        select(Appointment).where(
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.RESCHEDULED])
        )
    ).all()
    due = []
    for appointment in appointments:
        appointment_dt = datetime.combine(appointment.date, appointment.time, tzinfo=UTC)
        if start <= appointment_dt <= end:
            due.append(_appointment_read(appointment))
    return due


@app.post("/api/notifications")
def create_notification(payload: NotificationCreate, db: Db) -> dict[str, str]:
    item = Notification(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"notificationId": item.notification_id, "status": item.status}


@app.get("/api/audit")
def list_audit(db: Db) -> list[dict]:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all()
    return [
        {
            "auditId": event.audit_id,
            "eventType": event.event_type,
            "actorId": event.actor_id,
            "payload": event.payload,
            "createdAt": event.created_at.isoformat(),
        }
        for event in events
    ]


async def _lookup_crm(payload: PatientLookupRequest) -> dict:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                f"{settings.crm_mock_url}/crm/patients/lookup",
                json=payload.model_dump(),
            )
            response.raise_for_status()
            return response.json()
    except Exception:
        return {"exists": False, "crmPatientId": None, "name": "Пациент"}


async def _publish(subject: str, key: str, payload: dict) -> None:
    await publisher.publish(subject, event_for(subject, key, payload))


def _available_slot_or_409(db: Session, slot_id: str) -> Slot:
    slot = db.get(Slot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.status != "available":
        raise HTTPException(status_code=409, detail="Slot is not available")
    return slot


def _appointment_or_404(db: Session, appointment_id: str) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


def _reschedule_or_404(db: Session, approval_request_id: str) -> RescheduleRequest:
    request = db.get(RescheduleRequest, approval_request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Reschedule request not found")
    return request


def _user_read(user: User) -> UserRead:
    return UserRead(
        user_id=user.user_id,
        telegram_user_id=user.telegram_user_id,
        chat_id=user.chat_id,
        username=user.username,
        phone=user.phone,
        role=user.role,
        is_registered=True,
    )


def _patient_read(patient: Patient) -> PatientRead:
    return PatientRead(
        patient_id=patient.patient_id,
        crm_patient_id=patient.crm_patient_id,
        telegram_user_id=patient.telegram_user_id,
        name=patient.name,
        phone=patient.phone,
        is_primary=patient.is_primary,
    )


def _doctor_read(doctor: Doctor) -> DoctorRead:
    return DoctorRead(
        doctor_id=doctor.doctor_id,
        name=doctor.name,
        specialty=doctor.specialty,
        telegram_user_id=doctor.telegram_user_id,
        accepts_primary=doctor.accepts_primary,
    )


def _service_read(service: ClinicService) -> ServiceRead:
    return ServiceRead(
        service_id=service.service_id,
        doctor_id=service.doctor_id,
        name=service.name,
        category=service.category,
        price=service.price,
        currency=service.currency,
        duration_minutes=service.duration_minutes,
    )


def _slot_read(slot: Slot) -> SlotRead:
    return SlotRead(
        slot_id=slot.slot_id,
        doctor_id=slot.doctor_id,
        date=slot.date,
        time=slot.time,
        duration_minutes=slot.duration_minutes,
        status=slot.status,
        reserved_until=slot.reserved_until,
    )


def _appointment_read(appointment: Appointment) -> AppointmentRead:
    return AppointmentRead(
        appointment_id=appointment.appointment_id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        service_id=appointment.service_id,
        slot_id=appointment.slot_id,
        visit_type=appointment.visit_type,
        status=appointment.status,
        date=appointment.date,
        time=appointment.time,
    )


def _reschedule_read(request: RescheduleRequest) -> RescheduleRead:
    return RescheduleRead(
        approval_request_id=request.approval_request_id,
        appointment_id=request.appointment_id,
        requested_by=request.requested_by,
        old_slot_id=request.old_slot_id,
        proposed_slot_id=request.proposed_slot_id,
        status=request.status,
        expires_at=request.expires_at,
    )


if __name__ == "__main__":
    uvicorn.run("services.core_api.main:app", host="0.0.0.0", port=8000)
