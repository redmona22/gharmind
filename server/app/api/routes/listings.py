import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select

from app.api.deps import ADMINS, CurrentUser, current_user, get_db, require_roles
from app.core.audit import audit
from app.db.models import Listing
from app.schemas.listing import ListingIn
from app.utils.listing_import import MAX_BYTES, ImportFileError, parse_workbook

router = APIRouter(tags=["listings"])


def _out(r: Listing) -> dict:
    return {
        "id": str(r.id), "listing_type": r.listing_type, "project": r.project, "price": r.price,
        "deposit": r.deposit, "bhk": r.bhk, "area_sqft": r.area_sqft, "location": r.location,
        "furnishing": r.furnishing, "status": r.status, "rera_number": r.rera_number,
        # A sale listing with no RERA number is never shown to customers.
        "promotable": r.listing_type == "rent" or bool((r.rera_number or "").strip()),
    }


def _get(s, user: CurrentUser, listing_id: uuid.UUID) -> Listing:
    r = s.execute(
        select(Listing).where(Listing.id == listing_id, Listing.tenant_id == user.tenant_id)
    ).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, "not found")
    return r


@router.get("")
def list_listings(
    user: CurrentUser = Depends(current_user), s=Depends(get_db),
    type: str | None = Query(None, pattern="^(sale|rent)$"),
    status: str | None = Query(None, max_length=20),
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Listing).where(Listing.tenant_id == user.tenant_id)
    if type:
        stmt = stmt.where(Listing.listing_type == type)
    if status:
        stmt = stmt.where(Listing.status == status)
    if q:
        pat = "%" + q.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
        stmt = stmt.where(Listing.project.ilike(pat, escape="\\") | Listing.location.ilike(pat, escape="\\"))
    total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = s.execute(stmt.order_by(Listing.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return {"items": [_out(r) for r in rows], "total": total}


@router.post("/import")
async def import_listings(
    request: Request,
    commit: bool = Query(False, description="false = preview only, true = save"),
    user: CurrentUser = Depends(require_roles(*ADMINS)),
    s=Depends(get_db),
):
    """Excel import. The request body is the raw .xlsx file.
    Preview (commit=false) checks every row and writes nothing.
    Commit (commit=true) saves all rows, or none if any row has an error."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        raise HTTPException(413, "file is too large (5 MB maximum)")
    data = await request.body()
    if not data:
        raise HTTPException(400, "no file received")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file is too large (5 MB maximum)")

    try:
        result = parse_workbook(data)
    except ImportFileError as e:
        raise HTTPException(422, str(e))

    items = result.pop("items")

    if not commit:
        return result

    if result["missing_columns"]:
        raise HTTPException(409, "the file is missing required columns: " + ", ".join(result["missing_columns"]))
    if result["error_count"]:
        raise HTTPException(409, f"fix the {result['error_count']} row(s) with errors first, nothing was imported")
    if not items:
        raise HTTPException(409, "the file has no listing rows")

    for item in items:
        s.add(Listing(tenant_id=user.tenant_id, **item))
    s.flush()
    audit(s, user.tenant_id, str(user.id), "listings_imported", {"count": len(items)})
    return {"imported": len(items)}


@router.post("", status_code=201)
def create_listing(body: ListingIn, user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db)):
    r = Listing(tenant_id=user.tenant_id, **body.model_dump())
    s.add(r)
    s.flush()
    audit(s, user.tenant_id, str(user.id), "listing_created", {"listing_id": str(r.id)})
    return _out(r)


@router.put("/{listing_id}")
def update_listing(
    listing_id: uuid.UUID, body: ListingIn,
    user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db),
):
    r = _get(s, user, listing_id)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    audit(s, user.tenant_id, str(user.id), "listing_updated", {"listing_id": str(r.id)})
    return _out(r)


@router.delete("/{listing_id}")
def withdraw_listing(listing_id: uuid.UUID, user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db)):
    """Withdraws the listing (kept for the record, never shown to customers)."""
    r = _get(s, user, listing_id)
    r.status = "withdrawn"
    audit(s, user.tenant_id, str(user.id), "listing_withdrawn", {"listing_id": str(r.id)})
    return _out(r)