from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.core_api.database import get_db
from services.core_api.demo_reset import reset_demo_db
from services.core_api.demo_scenario import run_demo_scenario
from services.core_api.models import (
    Appointment,
    AuditEvent,
    ClinicService,
    Doctor,
    Patient,
    Slot,
    User,
)
from shared.config import get_settings
from shared.security import safe_compare_digest

settings = get_settings()
router = APIRouter(prefix="/api/admin", tags=["admin"])

Db = Annotated[Session, Depends(get_db)]


def verify_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_TOKEN is not configured",
        )
    provided = x_admin_token or ""
    if not safe_compare_digest(provided, settings.admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


AdminAuth = Annotated[None, Depends(verify_admin_token)]


@router.get("/dashboard")
def admin_dashboard(_: AdminAuth, db: Db) -> dict:
    return {
        "patients": db.scalar(select(func.count()).select_from(Patient)) or 0,
        "appointments": db.scalar(select(func.count()).select_from(Appointment)) or 0,
        "appointmentsActive": db.scalar(
            select(func.count()).select_from(Appointment).where(Appointment.status.in_(["confirmed", "rescheduled"]))
        )
        or 0,
        "doctors": db.scalar(select(func.count()).select_from(Doctor)) or 0,
        "services": db.scalar(select(func.count()).select_from(ClinicService)) or 0,
        "slotsAvailable": db.scalar(
            select(func.count()).select_from(Slot).where(Slot.status == "available")
        )
        or 0,
        "slotsBooked": db.scalar(
            select(func.count()).select_from(Slot).where(Slot.status != "available")
        )
        or 0,
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "auditEvents": db.scalar(select(func.count()).select_from(AuditEvent)) or 0,
        "clinicName": "Демо стоматология",
    }


@router.get("/patients")
def admin_patients(_: AdminAuth, db: Db) -> list[dict]:
    patients = db.scalars(select(Patient).order_by(Patient.created_at.desc())).all()
    return [
        {
            "patientId": p.patient_id,
            "name": p.name,
            "telegramUserId": p.telegram_user_id,
            "phone": p.phone,
            "isPrimary": p.is_primary,
            "createdAt": p.created_at.isoformat(),
        }
        for p in patients
    ]


@router.get("/appointments")
def admin_appointments(_: AdminAuth, db: Db) -> list[dict]:
    rows = db.scalars(select(Appointment).order_by(Appointment.date.desc(), Appointment.time.desc())).all()
    patient_names = {
        p.patient_id: p.name for p in db.scalars(select(Patient)).all()
    }
    doctor_names = {d.doctor_id: d.name for d in db.scalars(select(Doctor)).all()}
    service_names = {s.service_id: s.name for s in db.scalars(select(ClinicService)).all()}
    return [
        {
            "appointmentId": row.appointment_id,
            "patientName": patient_names.get(row.patient_id, row.patient_id),
            "doctorName": doctor_names.get(row.doctor_id, row.doctor_id),
            "serviceName": service_names.get(row.service_id, row.service_id),
            "date": row.date.isoformat(),
            "time": row.time.isoformat(timespec="minutes"),
            "status": row.status,
            "visitType": row.visit_type,
        }
        for row in rows
    ]


@router.get("/doctors")
def admin_doctors(_: AdminAuth, db: Db) -> list[dict]:
    return [
        {
            "doctorId": d.doctor_id,
            "name": d.name,
            "specialty": d.specialty,
            "acceptsPrimary": d.accepts_primary,
        }
        for d in db.scalars(select(Doctor)).all()
    ]


@router.get("/services")
def admin_services(_: AdminAuth, db: Db) -> list[dict]:
    return [
        {
            "serviceId": s.service_id,
            "name": s.name,
            "doctorId": s.doctor_id,
            "category": s.category,
            "price": s.price,
            "currency": s.currency,
        }
        for s in db.scalars(select(ClinicService)).all()
    ]


@router.get("/slots")
def admin_slots(_: AdminAuth, db: Db, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(Slot).order_by(Slot.date, Slot.time).limit(limit)
    ).all()
    return [
        {
            "slotId": s.slot_id,
            "doctorId": s.doctor_id,
            "date": s.date.isoformat(),
            "time": s.time.isoformat(timespec="minutes"),
            "status": s.status,
        }
        for s in rows
    ]


@router.get("/audit")
def admin_audit(_: AdminAuth, db: Db, limit: int = 100) -> list[dict]:
    events = db.scalars(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "auditId": e.audit_id,
            "eventType": e.event_type,
            "actorId": e.actor_id,
            "payload": e.payload,
            "createdAt": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.post("/demo/reset")
def admin_demo_reset(_: AdminAuth, db: Db) -> dict:
    return reset_demo_db(db)


@router.post("/demo/run")
async def admin_demo_run(_: AdminAuth, db: Db) -> dict:
    reset_info = reset_demo_db(db)
    bot_url = settings.bot_gateway_url or "http://127.0.0.1:8180"
    ai_url = settings.ai_orchestrator_url or "http://127.0.0.1:8101"
    core_url = settings.core_api_url or "http://127.0.0.1:8100"
    if "core-api:" in core_url:
        core_url = "http://127.0.0.1:8000"
    if "bot-gateway:" in bot_url:
        bot_url = "http://host.docker.internal:8180"
    if "ai-orchestrator:" in ai_url:
        ai_url = "http://ai-orchestrator:8001"
    result = await run_demo_scenario(core_url, bot_url, ai_url, skip_reset=True)
    result["reset"] = reset_info
    return result
