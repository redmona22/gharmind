from sqlalchemy import select

from app.agent.scoring import compute_score
from app.agent.tools.registry import ToolError, tool
from app.db.models import Contact

_ENUMS = {
    "language": {"en", "hi", "or"},
    "purpose": {"buy", "rent", "invest"},
    "financing": {"loan", "cash", "unsure"},
}
_INTS = {"budget_min", "budget_max", "bhk"}
_STRS = {"name": 200, "location_pref": 200, "timeline": 100}


@tool(
    "save_lead_info",
    "Save what you learned about the customer. Call whenever you learn a new fact. Only include fields you actually learned.",
    {
        "name": {"type": "string"},
        "language": {"type": "string", "enum": ["en", "hi", "or"]},
        "purpose": {"type": "string", "enum": ["buy", "rent", "invest"]},
        "budget_min": {"type": "integer", "description": "Rupees"},
        "budget_max": {"type": "integer", "description": "Rupees (monthly rent if renting)"},
        "location_pref": {"type": "string"},
        "bhk": {"type": "integer"},
        "timeline": {"type": "string", "description": "When they want to move, in their words"},
        "financing": {"type": "string", "enum": ["loan", "cash", "unsure"]},
    },
)
def save_lead_info(s, ctx, a: dict) -> dict:
    clean: dict = {}
    for key, value in a.items():
        if value in (None, ""):
            continue
        if key in _ENUMS:
            if value not in _ENUMS[key]:
                raise ToolError(f"{key} must be one of {sorted(_ENUMS[key])}")
            clean[key] = value
        elif key in _INTS:
            try:
                n = int(value)
            except (TypeError, ValueError):
                raise ToolError(f"{key} must be a whole number")
            if n <= 0 or (key == "bhk" and n > 10):
                raise ToolError(f"{key} is out of range")
            clean[key] = n
        elif key in _STRS:
            clean[key] = str(value).strip()[: _STRS[key]]
        # unknown keys are ignored

    if not clean:
        raise ToolError("nothing to save")

    contact = s.execute(
        select(Contact).where(Contact.id == ctx.contact_id, Contact.tenant_id == ctx.tenant_id)
    ).scalar_one()

    if "name" in clean:
        contact.name = clean.pop("name")
    if "language" in clean:
        contact.language = clean.pop("language")
    qual = dict(contact.qualification or {})
    qual.update(clean)
    contact.qualification = qual  # a new dict, so the JSON change is saved
    contact.lead_score = compute_score(qual)
    return {"saved": True, "lead_score": contact.lead_score}
