import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.assignment import auto_assign_new_lead
from app.core.idempotency import claim, complete, fail
from app.core.tenancy import tenant_session
from app.db.models import Contact, Conversation, Message
from app.workers.celery_app import celery_app
from app.workers.reply import enqueue_reply

log = logging.getLogger(__name__)


def _store_inbound(tenant_id: str, msg: dict) -> tuple[str, uuid.UUID | None]:
    """Store one inbound WhatsApp message, exactly once, however many times it is delivered.

    msg keys: wamid, from (+E164), type, text, timestamp, name
    Returns (status, conversation_id): status is "stored", "done" (duplicate) or "in_progress".
    """
    tid = uuid.UUID(tenant_id)
    key = f"wa-in:{msg['wamid']}"

    # Claim in its own short transaction so other workers see it immediately.
    with tenant_session(tid) as s:
        c = claim(s, tid, key, "whatsapp_inbound")
    if c.status == "done":
        cid = (c.result or {}).get("conversation_id")
        return "done", uuid.UUID(cid) if cid else None
    if c.status != "claimed":
        return c.status, None

    try:
        # Side effect and "done" mark in ONE transaction.
        with tenant_session(tid) as s:
            # RETURNING gives an id only when the contact is new (a conflict inserts nothing).
            new_contact_id = s.execute(
                pg_insert(Contact)
                .values(tenant_id=tid, phone=msg["from"], name=msg.get("name"), source="whatsapp")
                .on_conflict_do_nothing(index_elements=["tenant_id", "phone"])
                .returning(Contact.id)
            ).scalar_one_or_none()
            contact = s.execute(
                select(Contact).where(Contact.tenant_id == tid, Contact.phone == msg["from"])
            ).scalar_one()

            if new_contact_id is not None:
                # A failure here must never lose the customer's message, so it runs in a
                # savepoint: on error the lead simply stays unassigned.
                try:
                    with s.begin_nested():
                        auto_assign_new_lead(s, tid, contact.id)
                except Exception:
                    log.exception("auto-assign failed, lead stays unassigned")

            conv = s.execute(
                select(Conversation)
                .where(
                    Conversation.tenant_id == tid,
                    Conversation.contact_id == contact.id,
                    Conversation.status != "closed",
                )
                .order_by(Conversation.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if conv is None:
                conv = Conversation(tenant_id=tid, contact_id=contact.id, channel="whatsapp")
                s.add(conv)
                s.flush()
            conv.last_activity_at = datetime.now(timezone.utc)
            conv_id = conv.id

            content = msg.get("text") or f"[{msg.get('type', 'unknown')} message]"
            s.execute(
                pg_insert(Message)
                .values(
                    tenant_id=tid,
                    conversation_id=conv_id,
                    direction="in",
                    sender="client",
                    content=content,
                    wamid=msg["wamid"],
                )
                .on_conflict_do_nothing(index_elements=["tenant_id", "wamid"])
            )
            complete(s, tid, key, {"conversation_id": str(conv_id)})
    except Exception:
        with tenant_session(tid) as s:
            fail(s, tid, key)
        raise
    return "stored", conv_id


def handle_inbound_message(tenant_id: str, msg: dict) -> str:
    status, conv_id = _store_inbound(tenant_id, msg)
    # Also on "done": if we crashed after storing but before queueing, a duplicate delivery
    # repairs it. The reply task is idempotent, so an extra queue entry is harmless.
    if status in ("stored", "done") and conv_id is not None:
        enqueue_reply(tenant_id, str(conv_id), msg["wamid"])
    return status


@celery_app.task(name="process_inbound", bind=True, max_retries=5)
def process_inbound(self, tenant_id: str, msg: dict) -> str:
    try:
        return handle_inbound_message(tenant_id, msg)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(5 * 2**self.request.retries, 300))


def enqueue_message(tenant_id: str, msg: dict) -> None:
    process_inbound.delay(tenant_id, msg)