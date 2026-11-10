"""Handoff triggers. Decided in code, never left to the model."""
import re

# Checked in this order; first match wins.
_RULES = [
    ("minor", r"\bi'?m\s+(under\s+18|1[0-7])\b|\bi\s+am\s+(under\s+18|1[0-7])\b|\bmy\s+age\s+is\s+1[0-7]\b"),
    ("legal_or_complaint", r"\blegal\b|lawyer|advocate|\bcourt\b|complaint|fraud|cheat|scam|refund|\bpolice\b|consumer\s+forum"),
    ("price_negotiation", r"discount|negotiat|final\s+price|best\s+price|last\s+price|reduce\s+(the\s+)?price|price\s+kam|rate\s+kam|kitna\s+kam|thoda\s+kam|chhoot|chhut"),
    ("visit_request", r"site\s+visit|(want|like|wish)\s+to\s+(visit|see)|can\s+i\s+(visit|see)|book(ing)?\s+(it|this|the|a)\b|ready\s+to\s+(buy|book)"),
]
_INTEREST = re.compile(r"\bi'?m\s+interested\b|\bi\s+am\s+interested\b|interested\s+in\s+(buying|booking|this)", re.I)
_COMPILED = [(name, re.compile(p, re.I)) for name, p in _RULES]


def check_handoff(text: str, qualified: bool) -> str | None:
    """Return a reason code if a human must take over, else None.

    "I'm interested" only triggers once the buyer has shared a budget; before that
    it is just an opening line and the agent should qualify first.
    """
    text = text or ""
    for name, rx in _COMPILED:
        if rx.search(text):
            return name
    if qualified and _INTEREST.search(text):
        return "buying_intent"
    return None
