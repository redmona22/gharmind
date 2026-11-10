import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Tenant
from app.db.session import engine_owner
from app.main import app
from tests.conftest import _cleanup
from tests.dashboard.helpers import Company, make_lead, make_person


def _build_company(name: str) -> Company:
    tid = uuid.uuid4()
    with Session(engine_owner) as s:
        s.add(Tenant(id=tid, name=name))
        s.flush()
        admin = make_person(s, tid, "admin")
        sales1 = make_person(s, tid, "salesperson")
        sales2 = make_person(s, tid, "salesperson")
        lead1 = make_lead(s, tid, "Lead One", 40, sales1.id, "hello from one")
        lead2 = make_lead(s, tid, "Lead Two", 80, sales2.id, "hello from two")
        lead3 = make_lead(s, tid, "Lead Three", 10, None, "hello from three")
        s.commit()
    return Company(tid, admin, sales1, sales2, lead1, lead2, lead3)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def company():
    c = _build_company("Dash Co")
    yield c
    _cleanup(c.tenant_id)


@pytest.fixture()
def other_company():
    c = _build_company("Other Co")
    yield c
    _cleanup(c.tenant_id)
