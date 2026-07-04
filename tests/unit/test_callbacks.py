import pytest

from shared.callbacks import build_callback, parse_callback


def test_parse_slot_callback() -> None:
    action = parse_callback("slot:select:slot_doc_therapist_1_0")

    assert action.namespace == "slot"
    assert action.action == "select"
    assert action.args == ("slot_doc_therapist_1_0",)


def test_reject_callback_with_phone_number() -> None:
    with pytest.raises(ValueError):
        build_callback("appointment", "cancel", "+79990000000")


def test_reject_unknown_callback_namespace() -> None:
    with pytest.raises(ValueError):
        parse_callback("unknown:action")
