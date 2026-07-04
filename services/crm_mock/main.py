import random
from datetime import date

import uvicorn
from fastapi import FastAPI, HTTPException

from shared.config import get_settings
from shared.schemas import PatientLookupRequest

settings = get_settings()
app = FastAPI(title="Dental CRM/SRM Mock", version="0.1.0")

KNOWN_PATIENTS = {
    "+79991112233": {
        "patientId": "pat_existing",
        "crmPatientId": "crm_1001",
        "exists": True,
        "isPrimary": False,
        "name": "Иван Иванов",
        "lastVisitDate": str(date.today().replace(day=1)),
        "lastDoctorId": "doc_therapist",
    }
}

SYNCED_APPOINTMENTS: list[dict] = []


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/crm/patients/lookup")
def lookup_patient(payload: PatientLookupRequest) -> dict:
    if _should_fail():
        raise HTTPException(status_code=503, detail="CRM is temporarily unavailable")
    if payload.phone and payload.phone in KNOWN_PATIENTS:
        return KNOWN_PATIENTS[payload.phone]
    return {
        "patientId": None,
        "crmPatientId": None,
        "exists": False,
        "isPrimary": True,
        "name": "Пациент",
        "lastVisitDate": None,
        "lastDoctorId": None,
    }


@app.get("/crm/doctors")
def doctors() -> list[dict]:
    return [
        {"doctorId": "doc_therapist", "name": "Петров Петр Петрович"},
        {"doctorId": "doc_surgeon", "name": "Сидорова Анна Сергеевна"},
    ]


@app.get("/crm/services")
def services() -> list[dict]:
    return [
        {"serviceId": "svc_primary", "name": "Первичная консультация"},
        {"serviceId": "svc_secondary", "name": "Вторичный осмотр"},
        {"serviceId": "svc_caries", "name": "Лечение кариеса"},
        {"serviceId": "svc_hygiene", "name": "Профессиональная гигиена"},
        {"serviceId": "svc_extraction", "name": "Удаление зуба"},
    ]


@app.post("/crm/appointments/sync")
def sync_appointment(payload: dict) -> dict:
    if _should_fail():
        raise HTTPException(status_code=503, detail="CRM sync failed")
    crm_id = f"crm_apt_{len(SYNCED_APPOINTMENTS) + 9001}"
    SYNCED_APPOINTMENTS.append({"crmAppointmentId": crm_id, **payload})
    return {"crmAppointmentId": crm_id, "status": "synced"}


def _should_fail() -> bool:
    return random.random() < settings.crm_mock_failure_rate


if __name__ == "__main__":
    uvicorn.run("services.crm_mock.main:app", host="0.0.0.0", port=8002)
