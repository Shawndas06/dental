def staff_appointment_text(event_type: str, payload: dict) -> str:
    date = payload.get("date", "")
    time = (payload.get("time") or "")[:5]
    if event_type == "appointments.created":
        return f"Новая запись создана: {date} {time}."
    if event_type == "appointments.cancelled":
        return f"Запись отменена: {date} {time}."
    if event_type == "appointments.rescheduled.by_patient":
        return f"Пациент перенёс запись: {date} {time}."
    if event_type == "appointments.reschedule.requested_by_doctor":
        return "Врач запросил перенос записи. Ожидается одобрение пациента."
    if event_type == "appointments.reschedule.approved_by_patient":
        return f"Пациент одобрил перенос: {date} {time}."
    if event_type == "appointments.reschedule.rejected_by_patient":
        return "Пациент отклонил перенос записи."
    return f"Изменение записи: {date} {time}."


def patient_appointment_text(event_type: str, payload: dict) -> str | None:
    date = payload.get("date", "")
    time = (payload.get("time") or "")[:5]
    if event_type == "appointments.created":
        return f"Запись подтверждена: {date} {time}."
    if event_type == "appointments.cancelled":
        return f"Ваша запись отменена: {date} {time}."
    if event_type == "appointments.rescheduled.by_patient":
        return f"Запись перенесена: {date} {time}."
    if event_type == "appointments.reschedule.requested_by_doctor":
        return "Врач предложил перенести запись. Откройте «Мои записи» для решения."
    if event_type == "appointments.reschedule.approved_by_patient":
        return f"Перенос подтверждён: {date} {time}."
    if event_type == "appointments.reschedule.rejected_by_patient":
        return "Перенос отклонён. Текущая запись сохранена."
    return None
