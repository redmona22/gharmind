"""Pull lead facts out of a customer's own message with plain code.

The free local model often skips the save_lead_info tool, so this runs on every customer
message before the model does. It reads only the customer's words, never guesses, and returns
just the fields it is sure about, in the same shape save_lead_info takes.
Handles English and Hinglish in Roman script. Hindi and Odia script are not read yet.
"""
import re

_LAKH = 100_000
_CRORE = 10_000_000
_MIN_AMOUNT = 1_000
_MAX_AMOUNT = 1_000_000_000

_NUM = r"(\d+(?:\.\d+)?)"
_UNIT = r"(crores?|cr|lakhs?|lacs?|thousand|k)"

_RANGE = re.compile(rf"{_NUM}\s*{_UNIT}?\s*(?:-|\u2013|\u2014|to)\s*{_NUM}\s*{_UNIT}\b", re.I)
_SINGLE = re.compile(rf"{_NUM}\s*{_UNIT}\b", re.I)
_RUPEE_PREFIX = re.compile(r"(?:\u20b9|rs\.?|inr)\s*(\d[\d,]{3,})(?!\d)", re.I)
_RUPEE_SUFFIX = re.compile(r"(\d[\d,]{3,})\s*(?:rupees|rs|inr)\b", re.I)
_KEYWORD = re.compile(r"(?:budget|rent|price)[^\d\u20b9]{0,20}(\d[\d,]{4,})(?!\d)", re.I)

# Amounts that are about something other than the budget.
_SKIP_BEFORE = re.compile(r"(loan|emi|down ?payment|deposit|advance|interest|income|salary|earn)", re.I)
_SKIP_AFTER = re.compile(
    r"^\W*(?:as\s+)?(?:down ?payment|deposit|advance|emi|loan|salary|income|per year|annual|a year)", re.I
)

_BHK = re.compile(r"\b(\d{1,2})\s*-?\s*(?:bhk|bedrooms?|beds?)\b", re.I)

_INVEST = re.compile(r"\binvest(?:ment|ing)?\b", re.I)
_RENT = re.compile(r"\b(?:rent|rental|renting|lease|kiraye|kiraya)\b", re.I)
_BUY = re.compile(r"\b(?:buy|buying|purchase|purchasing|kharid\w*|for sale)\b", re.I)

_CASH = re.compile(
    r"\b(?:no loan|without (?:a )?loan|all cash|cash payment|pay (?:in )?cash|own funds|self[- ]funded)\b", re.I
)
_LOAN = re.compile(r"\b(?:home ?loan|housing loan|loan|financing|finance|mortgage)\b", re.I)

_TIMELINE = re.compile(
    r"\b(?:immediately|asap|right away|this month|next month|this week|next week"
    r"|(?:within|in)\s+\d+\s+(?:days?|weeks?|months?))\b",
    re.I,
)


def _multiplier(unit: str) -> int:
    u = unit.lower()
    if u.startswith("c"):
        return _CRORE
    if u.startswith("l"):
        return _LAKH
    return 1_000


def _ok(n: float) -> bool:
    return _MIN_AMOUNT <= n <= _MAX_AMOUNT


def _context_ok(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 25):start]
    after = text[end:end + 25]
    return not _SKIP_BEFORE.search(before) and not _SKIP_AFTER.search(after)


def _budget(text: str) -> dict:
    for m in _RANGE.finditer(text):
        unit_a, unit_b = m.group(2) or m.group(4), m.group(4)
        lo, hi = float(m.group(1)) * _multiplier(unit_a), float(m.group(3)) * _multiplier(unit_b)
        if lo <= hi and _ok(lo) and _ok(hi) and _context_ok(text, m.start(), m.end()):
            return {"budget_min": int(lo), "budget_max": int(hi)}

    for m in _SINGLE.finditer(text):
        value = float(m.group(1)) * _multiplier(m.group(2))
        if _ok(value) and _context_ok(text, m.start(), m.end()):
            return {"budget_max": int(value)}

    for pattern in (_RUPEE_PREFIX, _RUPEE_SUFFIX, _KEYWORD):
        for m in pattern.finditer(text):
            value = int(m.group(1).replace(",", ""))
            if _ok(value) and _context_ok(text, m.start(), m.end()):
                return {"budget_max": value}
    return {}


def extract_lead_facts(text: str) -> dict:
    """Facts the customer stated in this one message. Empty dict when nothing is clear."""
    if not text:
        return {}
    out: dict = {}
    out.update(_budget(text))

    m = _BHK.search(text)
    if m and 1 <= int(m.group(1)) <= 10:
        out["bhk"] = int(m.group(1))

    purposes = {
        p for p, rx in (("invest", _INVEST), ("rent", _RENT), ("buy", _BUY)) if rx.search(text)
    }
    if len(purposes) == 1:
        out["purpose"] = purposes.pop()

    if _CASH.search(text):
        out["financing"] = "cash"
    elif _LOAN.search(text):
        out["financing"] = "loan"

    m = _TIMELINE.search(text)
    if m:
        out["timeline"] = m.group(0).strip()[:100]
    return out