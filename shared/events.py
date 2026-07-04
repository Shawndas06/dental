from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


APPOINTMENT_STREAM_SUBJECTS = [
    "appointments.created",
    "appointments.cancelled",
    "appointments.rescheduled.by_patient",
    "appointments.reschedule.requested_by_doctor",
    "appointments.reschedule.approved_by_patient",
    "appointments.reschedule.rejected_by_patient",
]

NOTIFICATION_STREAM_SUBJECTS = [
    "notifications.patient.reminder_24h",
    "notifications.doctor.appointment_changed",
    "notifications.staff.appointment_changed",
]

CRM_STREAM_SUBJECTS = ["crm.appointment.sync_requested", "crm.appointment.sync_failed"]
AI_STREAM_SUBJECTS = ["ai.intake.low_confidence", "ai.output.validation_failed"]
AUDIT_STREAM_SUBJECTS = ["audit.events"]

STREAMS = {
    "APPOINTMENTS": APPOINTMENT_STREAM_SUBJECTS,
    "NOTIFICATIONS": NOTIFICATION_STREAM_SUBJECTS,
    "CRM_SYNC": CRM_STREAM_SUBJECTS,
    "REMINDERS": ["reminders.scan"],
    "AUDIT": AUDIT_STREAM_SUBJECTS + AI_STREAM_SUBJECTS,
}


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str = Field(default_factory=lambda: f"corr_{uuid4().hex}")
    idempotency_key: str
    payload: dict[str, Any]


def event_for(subject: str, idempotency_key: str, payload: dict[str, Any]) -> EventEnvelope:
    return EventEnvelope(
        event_type=subject,
        idempotency_key=idempotency_key,
        payload=payload,
    )
