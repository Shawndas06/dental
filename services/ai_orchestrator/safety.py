import re

from shared.schemas import IntakeResponse

FORBIDDEN_MEDICAL_PATTERNS = [
    r"\bдиагноз\b",
    r"\bлечи(те|ть|ться)?\b",
    r"\bпринимай(те)?\b",
    r"\bтаблетк",
    r"\bантибиотик",
    r"\bэто точно\b",
]

CLINICAL_QUESTION_PATTERNS = [
    r"\bдиагноз\b",
    r"\bболезн",
    r"\bлечи(те|ть|ться)?\b",
    r"\bтаблетк",
    r"\bантибиотик",
    r"\bчто у меня\b",
    r"\bнужно ли удал",
    r"\bфлюс\b",
    r"\bчем леч",
]


def is_clinical_question(text: str) -> bool:
    lowered = text.lower()
    if any(
        phrase in lowered
        for phrase in (
            "что у меня за болезнь",
            "какой диагноз",
            "чем лечить",
            "какие таблетки",
            "нужно ли удалять",
        )
    ):
        return True
    return any(re.search(pattern, lowered) for pattern in CLINICAL_QUESTION_PATTERNS)


def validate_ai_screen(response: IntakeResponse, allowed_service_ids: set[str], allowed_slot_ids: set[str]) -> None:
    text = response.text.lower()
    for pattern in FORBIDDEN_MEDICAL_PATTERNS:
        if re.search(pattern, text):
            raise ValueError("AI output contains clinical advice or diagnosis")

    service_id = response.route.get("serviceId")
    if service_id and service_id not in allowed_service_ids:
        raise ValueError("AI output references unknown service")

    for button in response.buttons:
        if button.callback_data.startswith("slot:select:"):
            slot_id = button.callback_data.removeprefix("slot:select:")
            if slot_id not in allowed_slot_ids:
                raise ValueError("AI output references unknown slot")


def safe_refusal() -> IntakeResponse:
    return IntakeResponse(
        intent="clinical_question",
        confidence=1.0,
        text=(
            "Я не могу ставить диагноз или назначать лечение. "
            "Можно записаться на консультацию, где врач осмотрит вас и ответит на вопросы."
        ),
        buttons=[
            {"text": "Записаться на консультацию", "callback_data": "appointment:start"},
            {"text": "Связаться с клиникой", "callback_data": "menu:contacts"},
        ],
        llm_called=False,
    )


def unknown_service_refusal() -> IntakeResponse:
    return IntakeResponse(
        intent="unknown_service",
        confidence=1.0,
        text=(
            "В доступных данных клиники такой услуги нет. "
            "Можно выбрать другую услугу или связаться с администратором."
        ),
        buttons=[
            {"text": "Показать услуги", "callback_data": "appointment:start"},
            {"text": "Связаться с клиникой", "callback_data": "menu:contacts"},
        ],
        llm_called=False,
    )


def low_confidence_fallback() -> IntakeResponse:
    return IntakeResponse(
        intent="low_confidence",
        confidence=0.3,
        text="Не хватает данных для безопасной маршрутизации. Выберите сценарий кнопками.",
        buttons=[
            {"text": "Записаться", "callback_data": "appointment:start"},
            {"text": "Цены", "callback_data": "pricing:list"},
            {"text": "Мои записи", "callback_data": "appointment:list"},
        ],
        llm_called=False,
    )
