from sqlalchemy import func, select

from app.agent.tools._common import load_listing
from app.agent.tools.registry import tool
from app.db.models import ListingMedia


@tool(
    "get_listing_details",
    "Get the full details of one property, using an id returned by search_listings. "
    "Quote only what this returns. Anything listed under not_recorded is unknown: say you will "
    "check with the team, never guess. If status is not 'available', tell the customer it is no "
    "longer available.",
    {"listing_id": {"type": "string", "description": "The id of a listing from search_listings"}},
    ["listing_id"],
)
def get_listing_details(s, ctx, a: dict) -> dict:
    r = load_listing(s, ctx, a.get("listing_id"))
    photo_count = s.execute(
        select(func.count(ListingMedia.id)).where(
            ListingMedia.listing_id == r.id, ListingMedia.tenant_id == ctx.tenant_id
        )
    ).scalar_one()

    wanted = ["price", "bhk", "area_sqft", "location", "furnishing"]
    if r.listing_type == "rent":
        wanted.append("deposit")
    not_recorded = [k for k in wanted if getattr(r, k) in (None, "")]

    out = {
        "id": str(r.id),
        "type": r.listing_type,
        "project": r.project,
        "location": r.location,
        "bhk": r.bhk,
        "area_sqft": r.area_sqft,
        "price": r.price,  # sale price, or monthly rent for a rental
        "deposit": r.deposit,
        "furnishing": r.furnishing,
        "status": r.status,
        "rera_number": r.rera_number if r.listing_type == "sale" else None,
        "photo_count": photo_count,
        "not_recorded": not_recorded,
    }
    if r.listing_type == "sale" and r.price and r.area_sqft:
        out["price_per_sqft"] = round(r.price / r.area_sqft)
    return out