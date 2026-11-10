import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import make_token
from app.db.models import Contact, User
from app.db.session import engine_owner
from app.main import app


def _headers(tid, user_id, role):
    return {"Authorization": f"Bearer {make_token('access', user_id, tid, 60, role=role)}"}


def _lead(tid, owner):
    with Session(engine_owner) as s:
        c = Contact(tenant_id=tid, phone=f"+9196{uuid.uuid4().int % 10**8:08d}", assigned_user_id=owner)
        s.add(c)
        s.commit()
        return c.id


def _name(user_id):
    with Session(engine_owner) as s:
        return s.execute(select(User.name).where(User.id == user_id)).scalar_one()


def test_lead_list_names_the_assignee(team_tenant):
    tid, ids = team_tenant
    mine = _lead(tid, ids["sales_a"])
    nobody = _lead(tid, None)

    r = TestClient(app).get("/leads?limit=100", headers=_headers(tid, ids["admin"], "admin"))

    by_id = {i["id"]: i for i in r.json()["items"]}
    assert by_id[str(mine)]["assigned_user_name"] == _name(ids["sales_a"])
    assert by_id[str(nobody)]["assigned_user_name"] is None


def test_lead_detail_names_the_assignee(team_tenant):
    tid, ids = team_tenant
    lead = _lead(tid, ids["sales_b"])

    r = TestClient(app).get(f"/leads/{lead}", headers=_headers(tid, ids["admin"], "admin"))

    assert r.status_code == 200 and r.json()["assigned_user_name"] == _name(ids["sales_b"])


def test_a_deactivated_assignee_is_still_named(team_tenant):
    tid, ids = team_tenant
    lead = _lead(tid, ids["sales_off"])  # the fixture's deactivated salesperson

    r = TestClient(app).get(f"/leads/{lead}", headers=_headers(tid, ids["admin"], "admin"))

    assert r.json()["assigned_user_name"] == _name(ids["sales_off"])


def test_a_salesperson_sees_their_own_name_on_their_lead(team_tenant):
    tid, ids = team_tenant
    lead = _lead(tid, ids["sales_a"])

    r = TestClient(app).get("/leads?limit=100", headers=_headers(tid, ids["sales_a"], "salesperson"))

    mine = [i for i in r.json()["items"] if i["id"] == str(lead)]
    assert mine and mine[0]["assigned_user_name"] == _name(ids["sales_a"])