"""Blocks any price or amount in a reply that did not come from this turn's tool results
(or from the customer's own words, or from the stored lead profile)."""
from datetime import date

from app.utils.numbers import extract_mentions

TOLERANCE = 0.0025  # 0.25%: lets "about 38,000" match an EMI of 37,962, nothing looser


def build_allowed(source_texts: list[str]) -> list[float]:
    allowed: list[float] = []
    for t in source_texts:
        allowed.extend(m.value for m in extract_mentions(t))
    year = date.today().year
    allowed.extend(float(y) for y in range(year - 1, year + 4))  # dates are fine to mention
    return allowed


def _is_allowed(value: float, allowed: list[float]) -> bool:
    return any(abs(value - a) <= max(a * TOLERANCE, 0.5) for a in allowed)


def checkable(reply: str):
    """Mentions that must be backed by data: any money-marked number, and any plain number >= 1000."""
    for m in extract_mentions(reply):
        if m.phone_like:
            continue
        if m.money or m.value >= 1000:
            yield m


def find_violations(reply: str, source_texts: list[str]) -> list[str]:
    allowed = build_allowed(source_texts)
    return [m.raw for m in checkable(reply) if not _is_allowed(m.value, allowed)]


def quoted_numbers(reply: str) -> list[str]:
    return [m.raw for m in checkable(reply)]
