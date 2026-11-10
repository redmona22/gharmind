_URGENT = ("immediate", "asap", "this month", "1 month", "30 days", "now", "week")


def compute_score(q: dict) -> int:
    """Lead score v1, 0-100: how much we know and how soon they want to move."""
    s = 0
    if q.get("budget_max") or q.get("budget_min"):
        s += 20
    if q.get("location_pref"):
        s += 10
    if q.get("bhk"):
        s += 10
    if q.get("purpose"):
        s += 15
    if q.get("financing") in ("loan", "cash"):
        s += 15
    timeline = str(q.get("timeline", "")).lower()
    if timeline:
        s += 10
        if any(w in timeline for w in _URGENT):
            s += 20
    return min(s, 100)
