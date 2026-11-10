import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Contact, Tenant, User
from app.db.session import SessionApp, engine_owner  # noqa: F401

_TENANT_TABLES = [
    "messages", "handoffs", "conversations", "consents", "contacts",
    "raw_events", "idempotency_keys", "audit_log", "users", "listings",
]


def _cleanup(*tenant_ids):
    with engine_owner.begin() as conn:
        for tid in tenant_ids:
            for table in _TENANT_TABLES:
                conn.execute(text(f"DELETE FROM {table} WHERE tenant_id = :t"), {"t": tid})
            conn.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})


class FakeLimiterStore:
    """In-memory stand-in for the Redis client used by the login rate limiter."""

    def __init__(self):
        self.data, self.ttls = {}, {}

    def incr(self, key):
        self.data[key] = int(self.data.get(key, 0)) + 1
        return self.data[key]

    def expire(self, key, seconds):
        self.ttls[key] = seconds

    def get(self, key):
        value = self.data.get(key)
        return None if value is None else str(value)

    def ttl(self, key):
        return self.ttls.get(key, -1) if key in self.data else -2

    def delete(self, key):
        self.data.pop(key, None)
        self.ttls.pop(key, None)


@pytest.fixture(autouse=True)
def _no_real_reply_queue(monkeypatch):
    """Tests never push jobs into the real Redis queue. Tests that care override this."""
    monkeypatch.setattr("app.workers.process_message.enqueue_reply", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _fresh_rate_limits(monkeypatch):
    """Every test starts with empty in-memory login counters, so tests never touch the real
    Redis and cannot lock each other out."""
    monkeypatch.setattr("app.core.rate_limit._store", FakeLimiterStore())


@pytest.fixture()
def two_tenants():
    """Seed two tenants with one contact each (as owner), clean up after."""
    a, b = uuid.uuid4(), uuid.uuid4()
    with Session(engine_owner) as s:
        s.add_all([Tenant(id=a, name="Tenant A"), Tenant(id=b, name="Tenant B")])
        s.flush()
        s.add_all([
            Contact(tenant_id=a, phone=f"+91900{uuid.uuid4().int % 10**7:07d}"),
            Contact(tenant_id=b, phone=f"+91800{uuid.uuid4().int % 10**7:07d}"),
        ])
        s.commit()
    yield a, b
    _cleanup(a, b)


@pytest.fixture()
def wa_tenant():
    """A tenant that owns a WhatsApp number. Yields (tenant_id, number)."""
    tid = uuid.uuid4()
    number = f"+9198{uuid.uuid4().int % 10**8:08d}"
    with Session(engine_owner) as s:
        s.add(Tenant(id=tid, name="WA Tenant", whatsapp_number=number))
        s.commit()
    yield tid, number
    _cleanup(tid)


@pytest.fixture()
def team_tenant():
    """A tenant with two active salespeople, one deactivated salesperson and one admin.
    Yields (tenant_id, {"sales_a": id, "sales_b": id, "sales_off": id, "admin": id})."""
    tid = uuid.uuid4()
    ids = {name: uuid.uuid4() for name in ("sales_a", "sales_b", "sales_off", "admin")}
    members = (
        ("sales_a", "salesperson", True),
        ("sales_b", "salesperson", True),
        ("sales_off", "salesperson", False),
        ("admin", "admin", True),
    )
    with Session(engine_owner) as s:
        s.add(Tenant(id=tid, name="Team Tenant"))
        s.flush()
        for name, role, active in members:
            s.add(User(
                id=ids[name], tenant_id=tid, email=f"{name}-{uuid.uuid4().hex[:8]}@example.test",
                name=name, role=role, password_hash="not-a-real-hash", active=active,
            ))
        s.commit()
    yield tid, ids
    _cleanup(tid)


@pytest.fixture()
def sync_webhook(monkeypatch):
    """Webhook secrets for tests, and run the worker inline instead of via Celery."""
    from app.config import settings
    from app.workers.process_message import handle_inbound_message

    monkeypatch.setattr(settings, "whatsapp_app_secret", "testsecret")
    monkeypatch.setattr(settings, "whatsapp_verify_token", "verify-me")
    monkeypatch.setattr("app.api.webhooks.whatsapp.enqueue_message", handle_inbound_message)