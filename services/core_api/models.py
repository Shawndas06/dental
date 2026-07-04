from datetime import UTC, date, datetime, time
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from services.core_api.database import Base


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: make_id("usr"))
    telegram_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    chat_id: Mapped[str] = mapped_column(String(64))
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(24), default="patient")


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: make_id("pat"))
    crm_patient_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="Пациент")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"

    doctor_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    crm_doctor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    specialty: Mapped[str] = mapped_column(String(120))
    telegram_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accepts_primary: Mapped[bool] = mapped_column(Boolean, default=True)


class ClinicService(Base, TimestampMixin):
    __tablename__ = "clinic_services"

    service_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    price: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)


class Slot(Base, TimestampMixin):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("doctor_id", "date", "time", name="uq_slot_time"),)

    slot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    time: Mapped[time] = mapped_column(Time)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(24), default="available", index=True)
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    appointment_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: make_id("apt")
    )
    crm_appointment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    patient_id: Mapped[str] = mapped_column(String(40), index=True)
    doctor_id: Mapped[str] = mapped_column(String(40), index=True)
    service_id: Mapped[str] = mapped_column(String(40), index=True)
    slot_id: Mapped[str] = mapped_column(String(40), index=True)
    visit_type: Mapped[str] = mapped_column(String(40), default="primary_consultation")
    status: Mapped[str] = mapped_column(String(40), default="confirmed", index=True)
    date: Mapped[date] = mapped_column(Date)
    time: Mapped[time] = mapped_column(Time)


class RescheduleRequest(Base, TimestampMixin):
    __tablename__ = "reschedule_requests"

    approval_request_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: make_id("apr")
    )
    appointment_id: Mapped[str] = mapped_column(String(40), index=True)
    requested_by: Mapped[str] = mapped_column(String(24))
    old_slot_id: Mapped[str] = mapped_column(String(40))
    proposed_slot_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="waiting_patient_approval")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: make_id("ntf")
    )
    chat_id: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(String(2000))
    kind: Mapped[str] = mapped_column(String(32), default="telegram")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    audit_id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: make_id("aud"))
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class IdempotencyRecord(Base, TimestampMixin):
    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    response: Mapped[dict] = mapped_column(JSON)
