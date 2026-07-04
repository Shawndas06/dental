from datetime import date, timedelta, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core_api.models import ClinicService, Doctor, Patient, Slot, User


DEMO_DOCTOR_DATA = [
    {
        "doctor_id": "doc_therapist",
        "crm_doctor_id": "crm_doc_001",
        "name": "Петров Петр Петрович",
        "specialty": "Стоматолог-терапевт",
        "telegram_user_id": "987654321",
        "accepts_primary": True,
    },
    {
        "doctor_id": "doc_surgeon",
        "crm_doctor_id": "crm_doc_002",
        "name": "Сидорова Анна Сергеевна",
        "specialty": "Стоматолог-хирург",
        "telegram_user_id": "987654322",
        "accepts_primary": True,
    },
]

DEMO_SERVICE_DATA = [
    {
        "service_id": "svc_primary",
        "doctor_id": "doc_therapist",
        "name": "Первичная консультация",
        "category": "consultation",
        "price": 1500,
        "duration_minutes": 60,
    },
    {
        "service_id": "svc_secondary",
        "doctor_id": "doc_therapist",
        "name": "Вторичный осмотр",
        "category": "consultation",
        "price": 900,
        "duration_minutes": 30,
    },
    {
        "service_id": "svc_caries",
        "doctor_id": "doc_therapist",
        "name": "Лечение кариеса",
        "category": "therapy",
        "price": 5200,
        "duration_minutes": 90,
    },
    {
        "service_id": "svc_hygiene",
        "doctor_id": "doc_therapist",
        "name": "Профессиональная гигиена",
        "category": "hygiene",
        "price": 4200,
        "duration_minutes": 60,
    },
    {
        "service_id": "svc_extraction",
        "doctor_id": "doc_surgeon",
        "name": "Удаление зуба",
        "category": "surgery",
        "price": 6000,
        "duration_minutes": 60,
    },
]


def seed_demo_data(db: Session) -> None:
    if not db.execute(select(Doctor)).first():
        db.add_all(Doctor(**item) for item in DEMO_DOCTOR_DATA)
    if not db.execute(select(ClinicService)).first():
        db.add_all(ClinicService(**item) for item in DEMO_SERVICE_DATA)
    if not db.execute(select(Slot)).first():
        db.add_all(_build_slots())
    if not db.execute(select(User).where(User.telegram_user_id == "demo_patient")).first():
        db.add(
            User(
                telegram_user_id="demo_patient",
                chat_id="demo_patient",
                username="demo_patient",
                role="patient",
            )
        )
        db.add(
            Patient(
                patient_id="pat_demo",
                crm_patient_id=None,
                telegram_user_id="demo_patient",
                name="Демо Пациент",
                phone="+79990000000",
                is_primary=True,
            )
        )
    db.commit()


def _build_slots() -> list[Slot]:
    slots: list[Slot] = []
    today = date.today()
    times = [time(10, 0), time(11, 30), time(14, 0), time(15, 30)]
    for day_offset in range(1, 15):
        current_date = today + timedelta(days=day_offset)
        if current_date.weekday() >= 5:
            continue
        for doctor_id in ("doc_therapist", "doc_surgeon"):
            for index, slot_time in enumerate(times):
                slots.append(
                    Slot(
                        slot_id=f"slot_{doctor_id}_{day_offset}_{index}",
                        doctor_id=doctor_id,
                        date=current_date,
                        time=slot_time,
                        duration_minutes=60,
                        status="available",
                    )
                )
    return slots


def clinic_profile() -> dict:
    return {
        "clinicId": "clinic_demo",
        "name": "Демо стоматология",
        "phone": "+79990000000",
        "services": [
            {
                "serviceId": service["service_id"],
                "doctorId": service["doctor_id"],
                "name": service["name"],
                "category": service["category"],
                "price": service["price"],
                "currency": "RUB",
                "durationMinutes": service["duration_minutes"],
            }
            for service in DEMO_SERVICE_DATA
        ],
        "equipment": ["радиовизиограф", "коффердам", "апекслокатор"],
        "technologies": ["цифровой снимок", "профессиональная гигиена"],
        "restrictions": [
            "AI не ставит диагноз",
            "Запись создается только по кнопке конкретного слота",
        ],
    }
