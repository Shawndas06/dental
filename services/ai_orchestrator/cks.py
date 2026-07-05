from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    intent: str
    specialty: str
    doctor_id: str
    service_id: str
    visit_type: str
    duration_minutes: int
    confidence: float


PAIN_WORDS = {"болит", "боль", "ноет", "зуб", "зубы", "десна", "слева", "справа"}
HYGIENE_WORDS = {"чистка", "гигиена", "налет", "камень"}
SURGERY_WORDS = {"удалить", "удаление", "зуб мудрости", "хирург"}
SECONDARY_WORDS = {"повторный", "осмотр", "после лечения", "контроль"}
UNKNOWN_SERVICE_WORDS = {"имплант", "имплантация", "брекеты", "элайнеры", "отбеливание", "томография"}


def classify_text(text: str) -> str:
    normalized = text.lower()
    if any(word in normalized for word in ("что у меня", "диагноз", "болезнь", "чем лечить")):
        return "clinical_question"
    if any(word in normalized for word in UNKNOWN_SERVICE_WORDS):
        return "unknown_service"
    if any(word in normalized for word in PAIN_WORDS | HYGIENE_WORDS | SURGERY_WORDS | SECONDARY_WORDS):
        return "appointment_intake"
    return "low_confidence"


def route_text(text: str) -> Route:
    normalized = text.lower()
    if any(word in normalized for word in SURGERY_WORDS):
        return Route(
            intent="appointment_intake",
            specialty="Стоматолог-хирург",
            doctor_id="doc_surgeon",
            service_id="svc_extraction",
            visit_type="extraction",
            duration_minutes=60,
            confidence=0.86,
        )
    if any(word in normalized for word in HYGIENE_WORDS):
        return Route(
            intent="appointment_intake",
            specialty="Стоматолог-терапевт",
            doctor_id="doc_therapist",
            service_id="svc_hygiene",
            visit_type="hygiene",
            duration_minutes=60,
            confidence=0.84,
        )
    if any(word in normalized for word in SECONDARY_WORDS):
        return Route(
            intent="appointment_intake",
            specialty="Стоматолог-терапевт",
            doctor_id="doc_therapist",
            service_id="svc_secondary",
            visit_type="secondary_visit",
            duration_minutes=30,
            confidence=0.82,
        )
    return Route(
        intent="appointment_intake",
        specialty="Стоматолог-терапевт",
        doctor_id="doc_therapist",
        service_id="svc_primary",
        visit_type="primary_consultation",
        duration_minutes=60,
        confidence=0.88,
    )
