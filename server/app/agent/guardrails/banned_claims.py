import re

_PATTERNS = [
    r"guarantee[ds]?\s+(returns?|profits?|appreciation|rental|income)",
    r"assured\s+(returns?|profits?|income)",
    r"best\s+investment",
    r"risk[\s-]?free",
    r"no\s+risk",
    r"100\s*%\s*(safe|secure|guaranteed|sure)",
    r"(prices?|rates?)\s+(will|is going to|are going to)\s+(definitely\s+)?(go up|increase|double|rise|shoot up)",
    r"double\s+your\s+money",
    r"can'?t\s+go\s+wrong",
    r"sure\s+(profit|returns?)",
]
_RX = [re.compile(p, re.I) for p in _PATTERNS]


def find_banned(reply: str) -> list[str]:
    return [m.group(0) for rx in _RX for m in [rx.search(reply or "")] if m]
