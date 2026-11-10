import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import make_token
from app.db.models import Listing, ListingMedia, Tenant
from app.db.session import engine_owner
from app.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
OCTET = {"Content-Type": "application/octet-stream"}


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    """Photos go to a throwaway folder during tests."""
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    return tmp_path


def _headers(tid, user_id, role):
    return {"Authorization": f"Bearer {make_token('access', user_id, tid, 60, role=role)}"}


def _listing(tid):
    with Session(engine_owner) as s:
        r = Listing(tenant_id=tid, listing_type="rent", project="Test Heights", price=15000)
        s.add(r)
        s.flush()
        lid = r.id
        s.commit()
        return lid


def _upload(client, tid, ids, lid, data=PNG, name="front.png"):
    return client.post(
        f"/listings/{lid}/media?filename={name}", content=data,
        headers={**_headers(tid, ids["admin"], "admin"), **OCTET},
    )


def test_upload_list_download_roundtrip(team_tenant):
    tid, ids = team_tenant
    lid, client = _listing(tid), TestClient(app)

    r = _upload(client, tid, ids, lid)
    assert r.status_code == 201
    body = r.json()
    assert body["content_type"] == "image/png" and body["filename"] == "front.png"

    listed = client.get(f"/listings/{lid}/media", headers=_headers(tid, ids["admin"], "admin"))
    assert [m["id"] for m in listed.json()["items"]] == [body["id"]]

    f = client.get(f"/listings/{lid}/media/{body['id']}/file", headers=_headers(tid, ids["admin"], "admin"))
    assert f.status_code == 200 and f.content == PNG
    assert f.headers["content-type"] == "image/png"
    assert f.headers["x-content-type-options"] == "nosniff"


def test_rejects_non_images_and_oversize_and_too_many(team_tenant):
    tid, ids = team_tenant
    lid, client = _listing(tid), TestClient(app)

    # A text file renamed to .png is refused: the bytes are checked, not the name.
    assert _upload(client, tid, ids, lid, data=b"hello, not an image", name="x.png").status_code == 422
    assert _upload(client, tid, ids, lid, data=b"<svg onload=alert(1)>", name="x.svg").status_code == 422
    big = b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024)
    assert _upload(client, tid, ids, lid, data=big).status_code == 413
    assert _upload(client, tid, ids, lid, data=b"").status_code == 400

    for _ in range(10):
        assert _upload(client, tid, ids, lid).status_code == 201
    assert _upload(client, tid, ids, lid).status_code == 409


def test_salesperson_can_view_but_not_change(team_tenant):
    tid, ids = team_tenant
    lid, client = _listing(tid), TestClient(app)
    media_id = _upload(client, tid, ids, lid).json()["id"]
    sales = _headers(tid, ids["sales_a"], "salesperson")

    assert client.get(f"/listings/{lid}/media", headers=sales).status_code == 200
    assert client.get(f"/listings/{lid}/media/{media_id}/file", headers=sales).status_code == 200
    assert client.post(f"/listings/{lid}/media", content=PNG, headers={**sales, **OCTET}).status_code == 403
    assert client.delete(f"/listings/{lid}/media/{media_id}", headers=sales).status_code == 403


def test_needs_login(team_tenant):
    tid, ids = team_tenant
    lid, client = _listing(tid), TestClient(app)
    assert client.get(f"/listings/{lid}/media").status_code == 401
    assert client.post(f"/listings/{lid}/media", content=PNG, headers=OCTET).status_code == 401


def test_another_company_cannot_open_the_file(team_tenant):
    tid, ids = team_tenant
    with Session(engine_owner) as s:
        other = Tenant(name="Other Realty")
        s.add(other)
        s.flush()
        lst = Listing(tenant_id=other.id, listing_type="rent", project="Secret Towers", price=1)
        s.add(lst)
        s.flush()
        mid = uuid.uuid4()
        s.add(ListingMedia(id=mid, tenant_id=other.id, listing_id=lst.id, filename="x.png",
                           content_type="image/png", size_bytes=1,
                           storage_key=f"{other.id}/{mid}.png", position=0))
        other_listing = lst.id
        s.commit()

    client = TestClient(app)
    admin = _headers(tid, ids["admin"], "admin")
    assert client.get(f"/listings/{other_listing}/media", headers=admin).status_code == 404
    assert client.get(f"/listings/{other_listing}/media/{mid}/file", headers=admin).status_code == 404
    assert client.delete(f"/listings/{other_listing}/media/{mid}", headers=admin).status_code == 404
    # Own listing id with the other company's media id is also a 404.
    own = _listing(tid)
    assert client.get(f"/listings/{own}/media/{mid}/file", headers=admin).status_code == 404


def test_delete_removes_row_and_file(team_tenant, _storage):
    tid, ids = team_tenant
    lid, client = _listing(tid), TestClient(app)
    media_id = _upload(client, tid, ids, lid).json()["id"]
    assert len(list(_storage.rglob("*.png"))) == 1

    r = client.delete(f"/listings/{lid}/media/{media_id}", headers=_headers(tid, ids["admin"], "admin"))

    assert r.status_code == 200
    assert list(_storage.rglob("*.png")) == []
    with Session(engine_owner) as s:
        assert s.execute(select(ListingMedia).where(ListingMedia.id == uuid.UUID(media_id))).first() is None

@pytest.fixture(autouse=True)
def _drop_other_company():
    """The isolation test creates a second company; remove it (and any left from earlier runs)."""
    yield
    from sqlalchemy import delete
    with Session(engine_owner) as s:
        for other_id in s.execute(select(Tenant.id).where(Tenant.name == "Other Realty")).scalars().all():
            s.execute(delete(ListingMedia).where(ListingMedia.tenant_id == other_id))
            s.execute(delete(Listing).where(Listing.tenant_id == other_id))
            s.execute(delete(Tenant).where(Tenant.id == other_id))
        s.commit()