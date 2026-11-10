import uuid

from sqlalchemy import select

from app.agent.tools.registry import ToolError
from app.db.models import Listing


def load_listing(s, ctx, raw_id) -> Listing:
    """A listing this company may talk about, or ToolError("listing not found").
    Withdrawn listings, other companies' listings and sale listings without a RERA number
    all look exactly like a missing listing, so the agent can never describe or promote them."""
    try:
        listing_id = uuid.UUID(str(raw_id))
    except (ValueError, TypeError, AttributeError):
        raise ToolError("listing_id must be an id returned by search_listings")
    r = s.execute(
        select(Listing).where(Listing.id == listing_id, Listing.tenant_id == ctx.tenant_id)
    ).scalar_one_or_none()
    if r is None or r.status == "withdrawn":
        raise ToolError("listing not found")
    if r.listing_type == "sale" and not (r.rera_number or "").strip():
        raise ToolError("listing not found")
    return r