from dataclasses import dataclass

MAX_CALLBACK_LENGTH = 64
ALLOWED_PREFIXES = {
    "menu",
    "appointment",
    "visit",
    "service",
    "doctor",
    "date",
    "slot",
    "reschedule",
    "calendar",
    "pricing",
    "staff",
    "nav",
    "register",
}


@dataclass(frozen=True)
class CallbackAction:
    namespace: str
    action: str
    args: tuple[str, ...] = ()

    @property
    def idempotency_key(self) -> str:
        return ":".join((self.namespace, self.action, *self.args))


def parse_callback(data: str) -> CallbackAction:
    if not data or len(data) > MAX_CALLBACK_LENGTH:
        raise ValueError("Invalid callback length")
    if any(char.isspace() for char in data):
        raise ValueError("Callback must not contain whitespace")

    parts = data.split(":")
    if len(parts) < 2:
        raise ValueError("Callback must include namespace and action")
    namespace, action, *args = parts
    if namespace not in ALLOWED_PREFIXES:
        raise ValueError("Unsupported callback namespace")
    if _contains_pii(data):
        raise ValueError("Callback must not contain personal data")
    return CallbackAction(namespace=namespace, action=action, args=tuple(args))


def build_callback(namespace: str, action: str, *args: str) -> str:
    data = ":".join((namespace, action, *args))
    parse_callback(data)
    return data


def _contains_pii(data: str) -> bool:
    digits = "".join(char for char in data if char.isdigit())
    return len(digits) >= 9 or "+" in data or "@" in data
