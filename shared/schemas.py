from datetime import date, datetime, time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AppointmentStatus(StrEnum):
    CONFIRMED = "confirmed"
    WAITING_PATIENT_APPROVAL = "waiting_patient_approval"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class VisitType(StrEnum):
    PRIMARY = "primary_consultation"
    SECONDARY = "secondary_visit"
    HYGIENE = "hygiene"
    EXTRACTION = "extraction"
    TREATMENT = "treatment"


class RescheduleStatus(StrEnum):
    WAITING_PATIENT_APPROVAL = "waiting_patient_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Button(BaseModel):
    text: str
    callback_data: str


class Screen(BaseModel):
    text: str
    buttons: list[Button] = Field(default_factory=list)
    button_layout: list[int] | None = None
    conversation_state: dict[str, Any] = Field(default_factory=dict)


class UserCreate(BaseModel):
    telegram_user_id: str
    chat_id: str
    username: str | None = None
    phone: str | None = None
    role: str = "patient"


class UserRead(UserCreate):
    user_id: str
    is_registered: bool = True


class PatientLookupRequest(BaseModel):
    phone: str | None = None
    telegram_user_id: str


class PatientQuickRegisterRequest(BaseModel):
    telegram_user_id: str
    chat_id: str
    name: str
    username: str | None = None
    phone: str | None = None


class PatientRead(BaseModel):
    patient_id: str
    crm_patient_id: str | None = None
    telegram_user_id: str
    name: str
    phone: str | None = None
    is_primary: bool = True


class DoctorRead(BaseModel):
    doctor_id: str
    name: str
    specialty: str
    telegram_user_id: str | None = None
    accepts_primary: bool = True


class ServiceRead(BaseModel):
    service_id: str
    doctor_id: str
    name: str
    category: str
    price: int
    currency: str = "RUB"
    duration_minutes: int = 60


class SlotRead(BaseModel):
    slot_id: str
    doctor_id: str
    date: date
    time: time
    duration_minutes: int
    status: str
    reserved_until: datetime | None = None


class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: str
    service_id: str
    slot_id: str
    visit_type: VisitType = VisitType.PRIMARY


class AppointmentRead(BaseModel):
    appointment_id: str
    patient_id: str
    doctor_id: str
    service_id: str
    slot_id: str
    visit_type: VisitType
    status: AppointmentStatus
    date: date
    time: time


class PatientRescheduleRequest(BaseModel):
    new_slot_id: str


class DoctorRescheduleRequest(BaseModel):
    proposed_slot_id: str
    doctor_id: str


class RescheduleRead(BaseModel):
    approval_request_id: str
    appointment_id: str
    requested_by: str
    old_slot_id: str
    proposed_slot_id: str
    status: RescheduleStatus
    expires_at: datetime


class IntakeRequest(BaseModel):
    telegram_user_id: str
    text: str
    phone: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class IntakeResponse(Screen):
    intent: str
    confidence: float
    llm_called: bool = False
    route: dict[str, Any] = Field(default_factory=dict)


class NotificationCreate(BaseModel):
    chat_id: str
    text: str
    kind: str = "telegram"
    payload: dict[str, Any] = Field(default_factory=dict)
