"""Сброс транзакционных данных для демо."""

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from services.core_api.models import (
    Appointment,
    AuditEvent,
    IdempotencyRecord,
    Notification,
    Patient,
    RescheduleRequest,
    Slot,
    User,
)

DEMO_TELEGRAM_IDS = {"demo_patient", "999000001"}


def reset_demo_db(db: Session) -> dict[str, int]:
    counts = {
        "appointments": db.scalar(select(func.count()).select_from(Appointment)) or 0,
        "reschedules": db.scalar(select(func.count()).select_from(RescheduleRequest)) or 0,
    }

    db.execute(delete(Appointment))
    db.execute(delete(RescheduleRequest))
    db.execute(delete(Notification))
    db.execute(delete(IdempotencyRecord))
    db.execute(delete(AuditEvent))
    db.execute(
        delete(Patient).where(Patient.telegram_user_id.not_in(DEMO_TELEGRAM_IDS))
    )
    db.execute(
        delete(User).where(User.telegram_user_id.not_in(DEMO_TELEGRAM_IDS))
    )
    db.execute(update(Slot).values(status="available", reserved_until=None))
    db.commit()

    return {
        "clearedAppointments": counts["appointments"],
        "clearedReschedules": counts["reschedules"],
        "slotsReset": db.scalar(select(func.count()).select_from(Slot)) or 0,
    }
