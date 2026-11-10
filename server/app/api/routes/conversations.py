import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update

from app.api.deps import ADMINS, CurrentUser, current_user, get_db
from app.core.audit import audit
from app.core.idempotency import claim, complete, fail
from app.core.tenancy import tenant_session
from app.db.models import Contact, Conversation, Handoff, Message
from app.integrations.whatsapp import SendError, get_sender
from app.schemas.conversation import SendIn
from app.workers.reply import REPLY_WINDOW

router = APIRouter(tags=["conversations"])


def load_conversation(s, user: CurrentUser, conversation_id: uuid.UUID):
    """The conversation and its contact, if the caller may see it. Otherwise a 404."""
    row = s.execute(
        select(Conversation, Contact)
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(Conversation.id == conversation_id, Conversation.tenant_id == user.tenant_id)
    ).first()
    if row is None:
        raise HTTPException(404, "not found")
    conv, contact = row
    if user.role == "salesperson" and contact.assigned_user_id != user.id:
        raise HTTPException(404, "not found")
    return conv, contact


@router.get("/{conversation_id}/messages")
def list_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=500),
    user: CurrentUser = Depends(current_user), s=Depends(get_db),
):
    conv, _ = load_conversation(s, user, conversation_id)
    rows = s.execute(
        select(Message)
        .where(Message.tenant_id == user.tenant_id, Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return {
        "conversation_id": str(conv.id),
        "status": conv.status,
        "items": [
            {"id": str(m.id), "direction": m.direction, "sender": m.sender, "content": m.content,
             "tool_used": m.tool_used, "created_at": m.created_at.isoformat()}
            for m in reversed(rows)
        ],
    }


@router.post("/{conversation_id}/takeover")
def takeover(conversation_id: uuid.UUID, user: CurrentUser = Depends(current_user), s=Depends(get_db)):
    """The human takes over. The agent stops replying in this conversation."""
    conv, _ = load_conversation(s, user, conversation_id)
    conv.status = "human"
    conv.assigned_user_id = user.id
    audit(s, user.tenant_id, str(user.id), "takeover", {"conversation_id": str(conv.id)})
    return {"status": "human", "assigned_user_id": str(user.id)}


@router.post("/{conversation_id}/release")
def release(conversation_id: uuid.UUID, user: CurrentUser = Depends(current_user), s=Depends(get_db)):
    """Hand the conversation back to the agent. Open handoffs are marked resolved."""
    conv, _ = load_conversation(s, user, conversation_id)
    if user.role == "salesperson" and conv.status == "human" and conv.assigned_user_id not in (None, user.id):
        raise HTTPException(403, "another team member is handling this conversation")
    s.execute(
        update(Handoff)
        .where(Handoff.tenant_id == user.tenant_id, Handoff.conversation_id == conv.id,
               Handoff.resolved.is_(False))
        .values(resolved=True)
    )
    conv.status = "agent"
    conv.assigned_user_id = None
    audit(s, user.tenant_id, str(user.id), "release", {"conversation_id": str(conv.id)})
    return {"status": "agent"}


@router.post("/{conversation_id}/messages", status_code=201)
def send_message(conversation_id: uuid.UUID, body: SendIn, user: CurrentUser = Depends(current_user)):
    """A human sends a WhatsApp reply. Safe to double-click: client_message_id makes it send once."""
    tid = user.tenant_id
    key = f"human-msg:{conversation_id}:{body.client_message_id}"

    with tenant_session(tid) as s:
        conv, contact = load_conversation(s, user, conversation_id)
        if contact.consent_status == "opted_out":
            raise HTTPException(403, "this customer has opted out of messages")
        if conv.status != "human":
            raise HTTPException(409, "take over the conversation before replying")
        if user.role not in ADMINS and conv.assigned_user_id != user.id:
            raise HTTPException(403, "another team member is handling this conversation")
        last_in = s.execute(
            select(func.max(Message.created_at)).where(
                Message.tenant_id == tid, Message.conversation_id == conv.id, Message.direction == "in"
            )
        ).scalar()
        if last_in is None or datetime.now(timezone.utc) - last_in > REPLY_WINDOW:
            raise HTTPException(409, "window_expired: more than 24 hours since the customer last wrote, "
                                     "a template message is needed")
        phone = contact.phone
        c = claim(s, tid, key, "human_message")

    if c.status == "done":
        return c.result
    if c.status == "in_progress":
        raise HTTPException(409, "this message is already being sent")

    try:
        out_wamid = get_sender().send_text(phone, body.text)
    except (SendError, RuntimeError) as e:
        with tenant_session(tid) as s:
            fail(s, tid, key)
        raise HTTPException(502, f"could not send the WhatsApp message: {e}")

    with tenant_session(tid) as s:
        msg = Message(
            tenant_id=tid, conversation_id=conversation_id, direction="out", sender="human",
            content=body.text, wamid=out_wamid,
        )
        s.add(msg)
        s.flush()
        conv = s.execute(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.tenant_id == tid)
        ).scalar_one()
        conv.last_activity_at = datetime.now(timezone.utc)
        audit(s, tid, str(user.id), "human_message", {"conversation_id": str(conversation_id)})
        result = {"message_id": str(msg.id), "wamid": out_wamid}
        complete(s, tid, key, result)
    return result
