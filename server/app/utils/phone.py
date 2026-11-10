import re


def digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def to_e164(value: str | None) -> str:
    """WhatsApp sends numbers without '+'. Store them as +<digits>."""
    d = digits(value)
    return f"+{d}" if d else ""