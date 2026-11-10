"""Answer one inbound message: run the agent, send the reply, store it. Exactly once."""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.agent.loop import run_agent
from app.agent.tools import ToolContext, execute_tool
from app.core.idempotency import claim, complete, fail
from app.core.tenancy import tenant_session
from app.db.models import Contact, Conversation, Message
from app.integrations.whatsapp import SendError, get_sender
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

# WhatsApp allows free-form replies only within 24 hours of the customer's last message.
REPLY_WINDOW = timedelta(hours=24)


@dataclass
class _Inbound:
    contact_id: uuid.UUID
    phone: str
    received_at: datetime
    is_latest: bool


def _inbound_info(tid: uuid.UUID, cid: uuid.UUID, wamid: str) -> _Inbound | None:
    with tenant_session(tid) as s:
        conv = s.execute(
            select(Conversation).where(Conversation.id == cid, Conversation.tenant_id == tid)
        ).scalar_one()
        contact = s.execute(
            select(Contact).where(Contact.id == conv.contact_id, Contact.tenant_id == tid)
        ).scalar_one()
        inbound = s.execute(
            select(Message).where(
                Message.tenant_id == tid, Message.conversation_id == cid,
                Message.wamid == wamid, Message.direction == "in",
            )
        ).scalar_one_or_none()
        if inbound is None:
            return None
        latest = s.execute(
            select(Message.id)
            .where(Message.tenant_id == tid, Message.conversation_id == cid)
            .order_by(Message.created_at.desc())
            .limit(1)
        ).scalar_one()
        return _Inbound(contact.id, contact.phone, inbound.created_at, latest == inbound.id)


def _finish(tid: uuid.UUID, key: str, result: dict) -> None:
    with tenant_session(tid) as s:
        complete(s, tid, key, result)


def handle_reply(tenant_id: str, conversation_id: str, inbound_wamid: str,
                 llm=None, sender=None) -> str:
    """Returns: sent | silent | superseded | window_expired | send_failed | missing_inbound
    | done (already handled) | in_progress (another worker has it)."""
    tid, cid = uuid.UUID(tenant_id), uuid.UUID(conversation_id)
    key = f"wa-reply:{inbound_wamid}"

    with tenant_session(tid) as s:
        c = claim(s, tid, key, "whatsapp_reply")
    if c.status != "claimed":
        return c.status

    try:
        info = _inbound_info(tid, cid, inbound_wamid)
        if info is None:
            _finish(tid, key, {"action": "missing_inbound"})
            return "missing_inbound"

        # A newer message arrived: its own task will answer both together.
        if not info.is_latest:
            _finish(tid, key, {"action": "superseded"})
            return "superseded"

        # The agent runs first, so an opt-out is honoured even if the reply window has passed.
        result = run_agent(tid, cid, llm)
        if result.reply is None:
            _finish(tid, key, {"action": result.action})
            return "silent"

        # Check again: a newer message may have landed while the model was thinking.
        latest_now = _inbound_info(tid, cid, inbound_wamid)
        if latest_now is None or not latest_now.is_latest:
            _finish(tid, key, {"action": "superseded"})
            return "superseded"

        if datetime.now(timezone.utc) - info.received_at > REPLY_WINDOW:
            if result.action == "reply":
                execute_tool(
                    "handoff_to_human",
                    {"reason": "window_expired",
                     "summary": "The 24-hour WhatsApp window had passed, so no free-form reply "
                                "could be sent. Contact the customer with an approved template."},
                    ToolContext(tid, info.contact_id, cid),
                )
            _finish(tid, key, {"action": "window_expired"})
            return "window_expired"

        sender = sender or get_sender()
        out_wamid = sender.send_text(info.phone, result.reply)

        # Store the sent message and mark the key done in ONE transaction.
        # Meta has no idempotency header for sends, so a crash exactly between the send and this
        # commit would resend on retry. That window is tiny; the audit log shows any repeat.
        with tenant_session(tid) as s:
            s.add(
                Message(
                    tenant_id=tid, conversation_id=cid, direction="out", sender="agent",
                    content=result.reply, wamid=out_wamid,
                    tool_used=",".join(result.tools_called) or None,
                )
            )
            conv = s.execute(
                select(Conversation).where(Conversation.id == cid, Conversation.tenant_id == tid)
            ).scalar_one()
            conv.last_activity_at = datetime.now(timezone.utc)
            complete(s, tid, key, {"action": result.action, "out_wamid": out_wamid})
        return "sent"

    except SendError as e:
        with tenant_session(tid) as s:
            fail(s, tid, key)
        if e.retryable:
            raise
        log.error("WhatsApp send failed permanently: %s", e)
        info = _inbound_info(tid, cid, inbound_wamid)
        if info is not None:
            execute_tool(
                "handoff_to_human",
                {"reason": "send_failed", "summary": f"Could not send the reply: {e}"},
                ToolContext(tid, info.contact_id, cid),
            )
        return "send_failed"
    except Exception:
        with tenant_session(tid) as s:
            fail(s, tid, key)
        raise


@celery_app.task(name="reply_to_inbound", bind=True, max_retries=5)
def reply_to_inbound(self, tenant_id: str, conversation_id: str, inbound_wamid: str) -> str:
    try:
        return handle_reply(tenant_id, conversation_id, inbound_wamid)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(5 * 2**self.request.retries, 300))


def enqueue_reply(tenant_id: str, conversation_id: str, inbound_wamid: str) -> None:
    reply_to_inbound.delay(tenant_id, conversation_id, inbound_wamid)
