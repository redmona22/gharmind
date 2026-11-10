from sqlalchemy import and_, or_, select

from app.agent.tools.registry import ToolError, tool
from app.db.models import Listing


def _int(args: dict, key: str) -> int | None:
    if args.get(key) in (None, ""):
        return None
    try:
        return int(args[key])
    except (TypeError, ValueError):
        raise ToolError(f"{key} must be a whole number")


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


@tool(
    "search_listings",
    "Search available properties. Returns real prices and details; quote only these.",
    {
        "listing_type": {"type": "string", "enum": ["sale", "rent"]},
        "max_price": {"type": "integer", "description": "Maximum price (sale) or monthly rent, in rupees"},
        "bhk": {"type": "integer"},
        "location": {"type": "string", "description": "Area, locality or project name"},
        "limit": {"type": "integer", "description": "Max results, up to 5"},
    },
)
def search_listings(s, ctx, a: dict) -> dict:
    q = select(Listing).where(Listing.tenant_id == ctx.tenant_id, Listing.status == "available")

    # RERA block: a sale project without a RERA number is never shown or promoted.
    q = q.where(
        or_(
            Listing.listing_type == "rent",
            and_(Listing.rera_number.is_not(None), Listing.rera_number != ""),
        )
    )

    if a.get("listing_type") in ("sale", "rent"):
        q = q.where(Listing.listing_type == a["listing_type"])
    if (max_price := _int(a, "max_price")) is not None:
        q = q.where(Listing.price <= max_price)
    if (bhk := _int(a, "bhk")) is not None:
        q = q.where(Listing.bhk == bhk)
    if loc := str(a.get("location") or "").strip():
        pat = f"%{_escape_like(loc)}%"
        q = q.where(
            or_(Listing.location.ilike(pat, escape="\\"), Listing.project.ilike(pat, escape="\\"))
        )

    limit = min(_int(a, "limit") or 5, 5)
    rows = s.execute(q.order_by(Listing.price.asc().nulls_last()).limit(limit)).scalars().all()
    return {
        "count": len(rows),
        "listings": [
            {
                "id": str(r.id),
                "type": r.listing_type,
                "project": r.project,
                "location": r.location,
                "bhk": r.bhk,
                "area_sqft": r.area_sqft,
                "price": r.price,
                "deposit": r.deposit,
                "furnishing": r.furnishing,
                "rera_number": r.rera_number if r.listing_type == "sale" else None,
            }
            for r in rows
        ],
    }
