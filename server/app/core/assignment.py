"""Automatic assignment of leads to salespeople.

A lead goes to the active salesperson with the fewest assigned leads. Ties go to the one
whose most recent lead is oldest, so assignments rotate. Admins and owners are never
picked. With no active salesperson the lead stays unassigned.
"""
import uuid

from sqlalchemy import func, select, text, update

from app.core.audit import audit
from app.db.models import Contact, Conversation, User


def lock_assignments(s, tenant_id: uuid.UUID) -> None:
    """One assignment job at a time per company, so two jobs cannot pick the same person.
    The lock is released when the transaction ends."""
    s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"lead-assign:{tenant_id}"})


def pick_salesperson(s, tenant_id: uuid.UUID) -> uuid.UUID | None:
    """The salesperson who should get the next lead, or None if the company has none."""
    owned = Contact.tenant_id == tenant_id, Contact.assigned_user_id == User.id
    load = select(func.count(Contact.id)).where(*owned).correlate(User).scalar_subquery()
    latest = select(func.max(Contact.created_at)).where(*owned).correlate(User).scalar_subquery()
    return s.execute(
        select(User.id)
        .where(User.tenant_id == tenant_id, User.role == "salesperson", User.active.is_(True))
        .order_by(load.asc(), latest.asc().nulls_first(), User.created_at.asc(), User.id.asc())
        .limit(1)
    ).scalar_one_or_none()


def auto_assign_new_lead(s, tenant_id: uuid.UUID, contact_id: uuid.UUID) -> uuid.UUID | None:
    """Assign a brand-new lead. Runs inside the caller's transaction."""
    lock_assignments(s, tenant_id)
    chosen = pick_salesperson(s, tenant_id)
    if chosen is None:
        return None
    contact = s.execute(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
    ).scalar_one()
    contact.assigned_user_id = chosen
    s.flush()
    audit(s, tenant_id, "system", "lead_auto_assigned",
          {"contact_id": str(contact_id), "assigned_to": str(chosen)})
    return chosen


def reassign_leads_from(s, tenant_id: uuid.UUID, leaving_user_id: uuid.UUID) -> int:
    """Hand every lead of a departing user to the remaining salespeople, one at a time, so
    the load spreads evenly. Chats they were handling follow their lead's new owner.
    Call after the user has been marked inactive. Returns how many leads moved.
    With no salesperson left, the leads become unassigned (admins still see them)."""
    lock_assignments(s, tenant_id)
    s.flush()
    contacts = s.execute(
        select(Contact)
        .where(Contact.tenant_id == tenant_id, Contact.assigned_user_id == leaving_user_id)
        .order_by(Contact.created_at)
    ).scalars().all()
    for contact in contacts:
        contact.assigned_user_id = pick_salesperson(s, tenant_id)
        s.flush()  # so the next pick sees this lead in the count

    new_owner = (
        select(Contact.assigned_user_id).where(Contact.id == Conversation.contact_id)
        .correlate(Conversation).scalar_subquery()
    )
    s.execute(
        update(Conversation)
        .where(Conversation.tenant_id == tenant_id, Conversation.assigned_user_id == leaving_user_id)
        .values(assigned_user_id=new_owner)
        .execution_options(synchronize_session=False)
    )
    return len(contacts)