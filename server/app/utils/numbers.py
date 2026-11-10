import re
from dataclasses import dataclass

_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_NUM = re.compile(
    r"(?P<cur>₹|rs\.?|inr)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*(?P<unit>crores?|lakhs?|lacs?|cr|k|l)(?![A-Za-z]))?",
    re.I,
)
_MULT = {
    "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5,
    "k": 1e3,
}


@dataclass
class Mention:
    raw: str          # as written, e.g. "₹45 lakh"
    value: float      # absolute value, e.g. 4500000.0
    money: bool       # had a currency sign or lakh/crore/k unit
    phone_like: bool  # 10+ plain digits (a phone number, not a price)


def extract_mentions(text: str) -> list[Mention]:
    text = _UUID.sub(" ", text or "")
    found = []
    for m in _NUM.finditer(text):
        digits = m.group("num").replace(",", "").rstrip(".")
        if not digits:
            continue
        try:
            value = float(digits)
        except ValueError:
            continue
        unit = (m.group("unit") or "").lower()
        if unit:
            value *= _MULT[unit]
        plain = "," not in m.group("num") and "." not in m.group("num")
        found.append(
            Mention(
                raw=m.group(0).strip(),
                value=value,
                money=bool(m.group("cur") or unit),
                phone_like=plain and len(digits) >= 10 and not unit and not m.group("cur"),
            )
        )
    return found
