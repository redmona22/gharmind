"""Plain-code readers for what a customer says: income, loan terms, project names, areas.

No database and no model here, so every rule is easy to test. The agent uses these to decide
which lookups to run before the model writes its reply.
"""
import re

_UNITS = {
    "k": 1_000, "thousand": 1_000,
    "l": 100_000, "lac": 100_000, "lacs": 100_000, "lakh": 100_000, "lakhs": 100_000,
    "cr": 10_000_000, "crore": 10_000_000, "crores": 10_000_000,
}
_AMOUNT = r"(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|cr|thousand|k|l)?\b"

_INCOME = re.compile(
    r"\b(?:income|salary|earn|earns|earning|earnings|take[- ]home|ctc)\b[^\d\n]{0,30}?" + _AMOUNT, re.I
)
_EXISTING_EMI = re.compile(
    r"\b(?:existing|current|ongoing|other)\s+(?:loan\s+)?(?:emis?|loans?)\b[^\d\n]{0,20}?" + _AMOUNT, re.I
)
_DOWN_1 = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:down\s*payment|downpayment|down|dp)\b", re.I)
_DOWN_2 = re.compile(r"\b(?:down\s*payment|downpayment)\b[^\d\n%]{0,15}?(\d+(?:\.\d+)?)\s*%", re.I)
_RATE_1 = re.compile(r"\b(?:interest|rate)\b[^\d\n]{0,20}?(\d+(?:\.\d+)?)\s*%?", re.I)
_RATE_2 = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:interest|rate|p\.?a\.?|per\s*annum)", re.I)
_RATE_3 = re.compile(r"\bat\s+(\d+(?:\.\d+)?)\s*%", re.I)
_YEARS_1 = re.compile(r"\b(?:for|over|tenure|tenor|period|term)\b[^\d\n]{0,12}?(\d{1,2})\s*(?:years?|yrs?)\b", re.I)
_YEARS_2 = re.compile(r"\b(\d{1,2})[- ]?(?:years?|yrs?)\s*(?:loan|tenure|tenor|term)\b", re.I)


def _money(m: re.Match) -> int:
    number = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    return round(number * _UNITS.get(unit, 1))


def _first(patterns, text):
    for p in patterns:
        m = p.search(text)
        if m:
            return m
    return None


def _terms_of(text: str) -> dict:
    out: dict = {}
    if m := _INCOME.search(text):
        value = _money(m)
        if 5_000 <= value <= 10_000_000_000:
            out["monthly_income"] = value
    if m := _EXISTING_EMI.search(text):
        value = _money(m)
        if 0 < value <= 10_000_000_000:
            out["existing_monthly_emi"] = value
    if m := _first((_DOWN_1, _DOWN_2), text):
        value = float(m.group(1))
        if 0 <= value < 100:
            out["down_payment_percent"] = value
    if m := _first((_RATE_2, _RATE_3, _RATE_1), text):
        value = float(m.group(1))
        if 1 <= value <= 30:
            out["annual_rate_percent"] = value
    if m := _first((_YEARS_1, _YEARS_2), text):
        value = int(m.group(1))
        if 1 <= value <= 30:
            out["years"] = value
    return out


def extract_finance_terms(texts: list[str]) -> dict:
    """Income and loan terms stated across the given customer messages (oldest first).
    A newer message overrides an older one, so "make it 9%" wins over an earlier 8.5%."""
    merged: dict = {}
    for t in texts:
        merged.update(_terms_of(t))
    return merged


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def _base_name(project: str) -> str:
    return _norm(re.sub(r"\(.*?\)", "", project))  # "Sunrise Heights (demo)" -> "sunrise heights"


def find_mentioned_projects(text: str, listings: list[tuple[str, str]]) -> list[str]:
    """Ids of the listings whose project name appears in the text. `listings` is (id, project)."""
    haystack = f" {_norm(text)} "
    hits = []
    for listing_id, project in listings:
        base = _base_name(project)
        if len(base) >= 4 and f" {base} " in haystack:
            hits.append(listing_id)
    return hits


def find_location(text: str, locations: list[str | None]) -> str | None:
    """An area from the company's own listings ("Patia" from "Patia, Bhubaneswar") that the
    text mentions. The longest match wins."""
    haystack = f" {_norm(text)} "
    best = None
    for loc in locations:
        if not loc:
            continue
        frag = _norm(loc.split(",")[0])
        if len(frag) >= 3 and f" {frag} " in haystack and (best is None or len(frag) > len(best)):
            best = frag
    return best