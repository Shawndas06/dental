from shared.notification_text import patient_appointment_text


def test_patient_created_notification() -> None:
    text = patient_appointment_text(
        "appointments.created",
        {"date": "2026-07-01", "time": "10:00:00"},
    )
    assert "подтверждена" in text.lower()


def test_patient_cancel_notification() -> None:
    text = patient_appointment_text(
        "appointments.cancelled",
        {"date": "2026-07-01", "time": "10:00:00"},
    )
    assert "отменена" in text.lower()


def test_unknown_event_returns_none() -> None:
    assert patient_appointment_text("appointments.unknown", {}) is None
