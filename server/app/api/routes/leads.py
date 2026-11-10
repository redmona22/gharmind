import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on

from app.api.deps import ADMINS, CurrentUser, current_user, get_db, require_roles, visible_contact
from app.core.audit import audit
from app.db.models import Contact, Conversation, Handoff, Message, User
from app.schemas.lead import AssignIn

router = APIRouter(tags=["leads"])


def _like(s: str) -> str:
    return "%" + s.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"


@router.get("")
def list_leads(
    user: CurrentUser = Depends(current_user),
    s=Depends(get_db),
    status: str | None = Query(None, description="conversation status: agent | human | closed"),
    score_min: int | None = Query(None, ge=0, le=100),
    q: str | None = Query(None, max_length=100, description="search name or phone"),
    assigned_to: str | None = Query(None, description="me | none | <user id> (admins only)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Contact).where(Contact.tenant_id == user.tenant_id)

    if user.role == "salesperson":
        stmt = stmt.where(Contact.assigned_user_id == user.id)  # only their own leads
    elif assigned_to == "none":
        stmt = stmt.where(Contact.assigned_user_id.is_(None))
    elif assigned_to == "me":
        stmt = stmt.where(Contact.assigned_user_id == user.id)
    elif assigned_to:
        try:
            stmt = stmt.where(Contact.assigned_user_id == uuid.UUID(assigned_to))
        except ValueError:
            raise HTTPException(422, "assigned_to must be me, none or a user id")

    if score_min is not None:
        stmt = stmt.where(Contact.lead_score >= score_min)
    if status:
        stmt = stmt.where(
            Contact.id.in_(
                select(Conversation.contact_id).where(
                    Conversation.tenant_id == user.tenant_id, Conversation.status == status
                )
            )
        )
    if q:
        pat = _like(q.strip())
        stmt = stmt.where(Contact.name.ilike(pat, escape="\\") | Contact.phone.ilike(pat, escape="\\"))

    total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    contacts = s.execute(
        stmt.order_by(Contact.lead_score.desc(), Contact.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    if not contacts:
        return {"items": [], "total": total}

    ids = [c.id for c in contacts]
    latest_conv: dict = {}
    for conv in s.execute(
        select(Conversation)
        .where(Conversation.tenant_id == user.tenant_id, Conversation.contact_id.in_(ids))
        .order_by(Conversation.created_at.desc())
    ).scalars():
        latest_conv.setdefault(conv.contact_id, conv)

    last_msg: dict = {}
    conv_ids = [c.id for c in latest_conv.values()]
    if conv_ids:
        for m in s.execute(
            select(Message)
            .ext(distinct_on(Message.conversation_id))
            .where(Message.tenant_id == user.tenant_id, Message.conversation_id.in_(conv_ids))
            .order_by(Message.conversation_id, Message.created_at.desc())
        ).scalars():
            last_msg[m.conversation_id] = m

    # Names of whoever each lead is assigned to (also for people who were deactivated since).
    owner_ids = {c.assigned_user_id for c in contacts if c.assigned_user_id}
    names: dict = {}
    if owner_ids:
        names = dict(
            s.execute(
                select(User.id, User.name).where(User.tenant_id == user.tenant_id, User.id.in_(owner_ids))
            ).all()
        )

    items = []
    for c in contacts:
        conv = latest_conv.get(c.id)
        msg = last_msg.get(conv.id) if conv else None
        items.append(
            {
                "id": str(c.id),
                "name": c.name,
                "phone": c.phone,
                "language": c.language,
                "source": c.source,
                "lead_score": c.lead_score,
                "consent_status": c.consent_status,
                "assigned_user_id": str(c.assigned_user_id) if c.assigned_user_id else None,
                "assigned_user_name": names.get(c.assigned_user_id),
                "conversation_id": str(conv.id) if conv else None,
                "conversation_status": conv.status if conv else None,
                "last_message": (
                    {"sender": msg.sender, "content": msg.content[:120], "at": msg.created_at.isoformat()}
                    if msg else None
                ),
                "created_at": c.created_at.isoformat(),
            }
        )
    return {"items": items, "total": total}


@router.get("/{contact_id}")
def lead_detail(contact_id: uuid.UUID, user: CurrentUser = Depends(current_user), s=Depends(get_db)):
    c = visible_contact(s, user, contact_id)
    convs = s.execute(
        select(Conversation).where(Conversation.tenant_id == user.tenant_id, Conversation.contact_id == c.id)
        .order_by(Conversation.created_at.desc())
    ).scalars().all()
    handoffs = s.execute(
        select(Handoff)
        .where(Handoff.tenant_id == user.tenant_id, Handoff.resolved.is_(False),
               Handoff.conversation_id.in_([x.id for x in convs] or [uuid.uuid4()]))
        .order_by(Handoff.created_at.desc())
    ).scalars().all()
    assignee_name = None
    if c.assigned_user_id:
        assignee_name = s.execute(
            select(User.name).where(User.id == c.assigned_user_id, User.tenant_id == user.tenant_id)
        ).scalar_one_or_none()
    return {
        "id": str(c.id),
        "name": c.name,
        "phone": c.phone,
        "language": c.language,
        "source": c.source,
        "lead_score": c.lead_score,
        "qualification": c.qualification or {},
        "consent_status": c.consent_status,
        "assigned_user_id": str(c.assigned_user_id) if c.assigned_user_id else None,
        "assigned_user_name": assignee_name,
        "conversations": [{"id": str(x.id), "status": x.status, "channel": x.channel} for x in convs],
        "open_handoffs": [
            {"id": str(h.id), "conversation_id": str(h.conversation_id), "reason": h.reason,
             "summary": h.summary, "created_at": h.created_at.isoformat()}
            for h in handoffs
        ],
    }


@router.patch("/{contact_id}/assign")
def assign_lead(
    contact_id: uuid.UUID, body: AssignIn,
    user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db),
):
    c = visible_contact(s, user, contact_id)
    if body.user_id is not None:
        target = s.execute(
            select(User).where(User.id == body.user_id, User.tenant_id == user.tenant_id, User.active.is_(True))
        ).scalar_one_or_none()
        if target is None:
            raise HTTPException(404, "that user does not exist in your company")
    c.assigned_user_id = body.user_id
    audit(s, user.tenant_id, str(user.id), "lead_assigned",
          {"contact_id": str(c.id), "assigned_to": str(body.user_id) if body.user_id else None})
    return {"id": str(c.id), "assigned_user_id": str(body.user_id) if body.user_id else None}