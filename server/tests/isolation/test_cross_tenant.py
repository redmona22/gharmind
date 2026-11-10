import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.tenancy import tenant_session
from app.db.models import Contact
from app.db.session import SessionApp


def test_tenant_sees_only_own_contacts(two_tenants):
    a, b = two_tenants
    with tenant_session(a) as s:
        rows = s.execute(select(Contact)).scalars().all()
    assert len(rows) == 1
    assert rows[0].tenant_id == a


def test_no_tenant_set_returns_nothing(two_tenants):
    with SessionApp() as s:
        assert s.execute(select(Contact)).scalars().all() == []


def test_cannot_read_other_tenant_by_id_filter(two_tenants):
    a, b = two_tenants
    with tenant_session(a) as s:
        rows = s.execute(select(Contact).where(Contact.tenant_id == b)).scalars().all()
    assert rows == []


def test_cannot_write_into_other_tenant(two_tenants):
    a, b = two_tenants
    with pytest.raises(DBAPIError):
        with tenant_session(a) as s:
            s.add(Contact(tenant_id=b, phone=f"+91700{uuid.uuid4().int % 10**7:07d}"))
            s.flush()


def test_app_role_cannot_bypass_rls():
    with SessionApp() as s:
        row = s.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    assert row.rolsuper is False and row.rolbypassrls is False