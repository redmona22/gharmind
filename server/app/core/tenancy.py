import uuid
from contextlib import contextmanager

from sqlalchemy import text

from app.db.session import SessionApp


@contextmanager
def tenant_session(tenant_id: uuid.UUID):
    """Open a DB session locked to one tenant.

    tenant_id must come from verified code (auth session or webhook-to-tenant
    mapping), never from the LLM or user text. The setting lasts for this
    transaction only; Postgres RLS then filters every query.
    """
    with SessionApp() as session:
        with session.begin():
            session.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            yield session


def resolve_tenant_by_whatsapp(number: str) -> uuid.UUID | None:
    """Map the receiving WhatsApp number to a tenant (id only, via a narrow DB function)."""
    with SessionApp() as session:
        return session.execute(
            text("SELECT resolve_tenant_by_whatsapp(:n)"), {"n": number}
        ).scalar()