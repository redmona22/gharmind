import uuid

from fastapi.testclient import TestClient

from app.core.security import make_token
from app.main import app


def _headers(tid, user_id, role):
    return {"Authorization": f"Bearer {make_token('access', user_id, tid, 60, role=role)}"}


def test_reactivated_person_can_use_the_app_again(team_tenant):
    tid, ids = team_tenant
    client = TestClient(app)
    off = _headers(tid, ids["sales_off"], "salesperson")
    assert client.get("/auth/me", headers=off).status_code == 401  # deactivated

    r = client.post(f"/users/{ids['sales_off']}/reactivate", headers=_headers(tid, ids["admin"], "admin"))
    assert r.status_code == 200 and r.json()["active"] is True
    assert client.get("/auth/me", headers=off).status_code == 200  # same token works again


def test_deactivate_then_reactivate_round_trip(team_tenant):
    tid, ids = team_tenant
    client = TestClient(app)
    admin = _headers(tid, ids["admin"], "admin")
    assert client.post(f"/users/{ids['sales_a']}/deactivate", headers=admin).json()["active"] is False
    assert client.post(f"/users/{ids['sales_a']}/reactivate", headers=admin).json()["active"] is True


def test_reactivating_an_active_person_changes_nothing(team_tenant):
    tid, ids = team_tenant
    r = TestClient(app).post(f"/users/{ids['sales_b']}/reactivate", headers=_headers(tid, ids["admin"], "admin"))
    assert r.status_code == 200 and r.json()["active"] is True


def test_salespeople_cannot_reactivate_anyone(team_tenant):
    tid, ids = team_tenant
    r = TestClient(app).post(f"/users/{ids['sales_off']}/reactivate", headers=_headers(tid, ids["sales_a"], "salesperson"))
    assert r.status_code == 403


def test_unknown_user_is_not_found(team_tenant):
    tid, ids = team_tenant
    r = TestClient(app).post(f"/users/{uuid.uuid4()}/reactivate", headers=_headers(tid, ids["admin"], "admin"))
    assert r.status_code == 404