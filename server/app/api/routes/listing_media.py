import uuid
from pathlib import PurePath

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select

from app.api.deps import ADMINS, CurrentUser, current_user, get_db, require_roles
from app.core.audit import audit
from app.core.storage import MAX_FILES_PER_LISTING, MAX_IMAGE_BYTES, detect_image, get_storage
from app.db.models import Listing, ListingMedia

router = APIRouter(tags=["listing-media"])


def _out(m: ListingMedia) -> dict:
    return {"id": str(m.id), "filename": m.filename, "content_type": m.content_type,
            "size_bytes": m.size_bytes}


def _clean_name(raw: str) -> str:
    name = PurePath(raw.replace("\\", "/")).name
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:150] or "photo"


def _listing(s, user: CurrentUser, listing_id: uuid.UUID, lock: bool = False) -> Listing:
    stmt = select(Listing).where(Listing.id == listing_id, Listing.tenant_id == user.tenant_id)
    if lock:
        stmt = stmt.with_for_update()  # two uploads at once cannot both slip past the limit
    r = s.execute(stmt).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, "not found")
    return r


def _media(s, user: CurrentUser, listing_id: uuid.UUID, media_id: uuid.UUID) -> ListingMedia:
    m = s.execute(
        select(ListingMedia).where(
            ListingMedia.id == media_id,
            ListingMedia.listing_id == listing_id,
            ListingMedia.tenant_id == user.tenant_id,
        )
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "not found")
    return m


@router.get("/{listing_id}/media")
def list_media(listing_id: uuid.UUID, user: CurrentUser = Depends(current_user), s=Depends(get_db)):
    _listing(s, user, listing_id)
    rows = s.execute(
        select(ListingMedia)
        .where(ListingMedia.listing_id == listing_id, ListingMedia.tenant_id == user.tenant_id)
        .order_by(ListingMedia.position, ListingMedia.created_at)
    ).scalars().all()
    return {"items": [_out(m) for m in rows]}


@router.post("/{listing_id}/media", status_code=201)
async def upload_media(
    listing_id: uuid.UUID,
    request: Request,
    filename: str = Query("photo", max_length=200),
    user: CurrentUser = Depends(require_roles(*ADMINS)),
    s=Depends(get_db),
):
    """The request body is the raw photo (JPEG, PNG or WebP, 5 MB maximum)."""
    _listing(s, user, listing_id, lock=True)

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES + 1024:
        raise HTTPException(413, "photo is too large (5 MB maximum)")
    data = await request.body()
    if not data:
        raise HTTPException(400, "no file received")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "photo is too large (5 MB maximum)")

    kind = detect_image(data)
    if kind is None:
        raise HTTPException(422, "only JPEG, PNG and WebP photos are allowed")
    content_type, ext = kind

    count = s.execute(
        select(func.count(ListingMedia.id)).where(
            ListingMedia.listing_id == listing_id, ListingMedia.tenant_id == user.tenant_id
        )
    ).scalar_one()
    if count >= MAX_FILES_PER_LISTING:
        raise HTTPException(409, f"a listing can have at most {MAX_FILES_PER_LISTING} photos")

    media_id = uuid.uuid4()
    key = f"{user.tenant_id}/{media_id}.{ext}"
    row = ListingMedia(
        id=media_id, tenant_id=user.tenant_id, listing_id=listing_id,
        filename=_clean_name(filename), content_type=content_type,
        size_bytes=len(data), storage_key=key, position=count,
    )
    s.add(row)
    s.flush()
    get_storage().save(key, data)  # if this fails the row is rolled back with the request
    audit(s, user.tenant_id, str(user.id), "listing_media_added",
          {"listing_id": str(listing_id), "media_id": str(media_id)})
    return _out(row)


@router.get("/{listing_id}/media/{media_id}/file")
def media_file(
    listing_id: uuid.UUID, media_id: uuid.UUID,
    user: CurrentUser = Depends(current_user), s=Depends(get_db),
):
    m = _media(s, user, listing_id, media_id)
    try:
        data = get_storage().read(m.storage_key)
    except FileNotFoundError:
        raise HTTPException(404, "file not found")
    return Response(
        content=data,
        media_type=m.content_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{listing_id}/media/{media_id}")
def delete_media(
    listing_id: uuid.UUID, media_id: uuid.UUID,
    user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db),
):
    m = _media(s, user, listing_id, media_id)
    key = m.storage_key
    s.delete(m)
    s.flush()
    get_storage().delete(key)
    audit(s, user.tenant_id, str(user.id), "listing_media_deleted",
          {"listing_id": str(listing_id), "media_id": str(media_id)})
    return {"deleted": True}