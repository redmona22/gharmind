import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.fallback import hold_message, opt_out_message
from app.db.models import Contact, Conversation, Message
from app.db.session import engine_owner
from app.integrations.whatsapp import SendError
from app.workers.process_message import handle_inbound_message
from app.workers.reply import handle_reply
from tests.agent.fakes import BrokenLLM, FailingSender, RecordingSender, ScriptedLLM, say
from tests.helpers import count


def seed_inbound(tid, message, wamid=None, language="en"):
    wamid = wamid or f"in-{uuid.uuid4()}"
    with Session(engine_owner) as s:
        c = Contact(tenant_id=tid, phone=f"+9199{uuid.uuid4().int % 10**8:08d}", language=language)
        s.add(c)
        s.flush()
        conv = Conversation(tenant_id=tid, contact_id=c.id)
        s.add(conv)
        s.flush()
        s.add(Message(tenant_id=tid, conversation_id=conv.id, direction="in", sender="client",
                      content=message, wamid=wamid))
        s.commit()
        return c.id, conv.id, wamid


def add_inbound(tid, conv, message, wamid=None):
    wamid = wamid or f"in-{uuid.uuid4()}"
    with Session(engine_owner) as s:  # its own transaction, so created_at is later
        s.add(Message(tenant_id=tid, conversation_id=conv, direction="in", sender="client",
                      content=message, wamid=wamid))
        s.commit()
    return wamid


def scalar(sql, **p):
    with engine_owner.connect() as conn:
        return conn.execute(text(sql), p).scalar()


def run(tid, conv, wamid, llm=None, sender=None):
    return handle_reply(str(tid), str(conv), wamid, llm=llm, sender=sender)


def test_reply_is_sent_and_stored_once(wa_tenant):
    tid, _ = wa_tenant
    _, conv, wamid = seed_inbound(tid, "Hi, I want a flat")
    sender = RecordingSender()
    llm = ScriptedLLM(say("Happy to help! What is your budget?"))

    assert run(tid, conv, wamid, llm, sender) == "sent"
    assert run(tid, conv, wamid, llm, sender) == "done"  # a retry changes nothing
    assert len(sender.sent) == 1 and sender.sent[0][1] == "Happy to help! What is your budget?"

    with engine_owner.connect() as c:
        assert count(c, "messages", tid) == 2
    out = scalar("SELECT content FROM messages WHERE conversation_id = :c AND direction = 'out'", c=conv)
    assert out == "Happy to help! What is your budget?"
    assert scalar("SELECT sender FROM messages WHERE conversation_id = :c AND direction = 'out'", c=conv) == "agent"


def test_five_workers_racing_send_exactly_one_reply(wa_tenant):
    tid, _ = wa_tenant
    _, conv, wamid = seed_inbound(tid, "Hello")
    sender = RecordingSender()
    llm = ScriptedLLM(say("Hi there! How can I help?"))
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: run(tid, conv, wamid, llm, sender), range(5)))
    assert results.count("sent") == 1
    assert len(sender.sent) == 1
    with engine_owner.connect() as c:
        assert count(c, "messages", tid) == 2


def test_retryable_send_failure_raises_and_a_retry_then_sends_once(wa_tenant):
    tid, _ = wa_tenant
    _, conv, wamid = seed_inbound(tid, "Hello")
    llm = ScriptedLLM(say("Hi there! How can I help?"))
    failing = FailingSender(retryable=True)
    with pytest.raises(SendError):
        run(tid, conv, wamid, llm, failing)

    good = RecordingSender()
    assert run(tid, conv, wamid, llm, good) == "sent"
    assert len(good.sent) == 1
    with engine_owner.connect() as c:
        assert count(c, "messages", tid) == 2  # the failed attempt stored nothing


def test_permanent_send_failure_alerts_a_human(wa_tenant):
    tid, _ = wa_tenant
    _, conv, wamid = seed_inbound(tid, "Hello")
    llm = ScriptedLLM(say("Hi there! How can I help?"))
    assert run(tid, conv, wamid, llm, FailingSender(retryable=False)) == "send_failed"
    assert scalar("SELECT reason FROM handoffs WHERE conversation_id = :c", c=conv) == "send_failed"
    with engine_owner.connect() as c:
        assert count(c, "messages", tid) == 1  # only the customer's message


def test_handoff_sends_the_holding_message(wa_tenant):
    tid, _ = wa_tenant
    _, conv, wamid = seed_inbound(tid, "Can you give me a discount?")
    sender = RecordingSender()
    assert run(tid, conv, wamid, BrokenLLM(), sender) == "sent"
    assert sender.sent[0][1] == hold_message("en")
    assert scalar("SELECT reason FROM handoffs WHERE conversation_id = :c", c=conv) == "price_negotiation"


def test_ai_outage_still_answers_the_customer(wa_tenant):
    tid, _ = wa_tenant
    _, conv, wamid = seed_inbound(tid, "Hello", language="hi")
    sender = RecordingSender()
    assert run(tid, conv, wamid, BrokenLLM(), sender) == "sent"
    assert sender.sent[0][1] == hold_message("hi")
    assert scalar("SELECT reason FROM handoffs WHERE conversation_id = :c", c=conv) == "ai_unavailable"


def test_stop_confirms_once_then_goes_quiet(wa_tenant):
    tid, _ = wa_tenant
    contact, conv, wamid = seed_inbound(tid, "STOP")
    sender = RecordingSender()
    assert run(tid, conv, wamid, BrokenLLM(), sender) == "sent"
    assert sender.sent[0][1] == opt_out_message("en")
    assert scalar("SELECT consent_status FROM contacts WHERE id = :c", c=contact) == "opted_out"

    later = add_inbound(tid, conv, "hello again?")
    assert run(tid, conv, later, BrokenLLM(), sender) == "silent"
    assert len(sender.sent) == 1


def test_silent_when_a_human_has_taken_over(wa_tenant):
    tid, _ = wa_tenant
    _, conv, wamid = seed_inbound(tid, "hello?")
    with engine_owner.begin() as c:
        c.execute(text("UPDATE conversations SET status = 'human' WHERE id = :c"), {"c": conv})
    sender = RecordingSender()
    assert run(tid, conv, wamid, BrokenLLM(), sender) == "silent"
    assert sender.sent == []


def test_older_message_is_skipped_when_a_newer_one_arrived(wa_tenant):
    tid, _ = wa_tenant
    _, conv, first = seed_inbound(tid, "Looking for a 2BHK")
    second = add_inbound(tid, conv, "in Patia please")
    sender = RecordingSender()
    llm = ScriptedLLM(say("Great, Patia it is. What is your budget?"))

    assert run(tid, conv, first, llm, sender) == "superseded"
    assert sender.sent == []
    assert run(tid, conv, second, llm, sender) == "sent"  # answers both messages together
    assert len(sender.sent) == 1


def test_no_free_form_reply_after_the_24_hour_window(wa_tenant):
    tid, _ = wa_tenant
    _, conv, wamid = seed_inbound(tid, "Hello")
    with engine_owner.begin() as c:
        c.execute(
            text("UPDATE messages SET created_at = now() - interval '30 hours' WHERE wamid = :w"),
            {"w": wamid},
        )
    sender = RecordingSender()
    llm = ScriptedLLM(say("Hi there! How can I help?"))
    assert run(tid, conv, wamid, llm, sender) == "window_expired"
    assert sender.sent == []
    assert scalar("SELECT reason FROM handoffs WHERE conversation_id = :c", c=conv) == "window_expired"


def test_missing_inbound_message_is_handled(wa_tenant):
    tid, _ = wa_tenant
    _, conv, _ = seed_inbound(tid, "Hello")
    assert run(tid, conv, "no-such-wamid", BrokenLLM(), RecordingSender()) == "missing_inbound"


def test_inbound_queues_a_reply_even_for_duplicate_deliveries(wa_tenant, monkeypatch):
    tid, _ = wa_tenant
    calls = []
    monkeypatch.setattr("app.workers.process_message.enqueue_reply", lambda t, c, w: calls.append((t, c, w)))
    msg = {"wamid": "wamid.ENQ", "from": "+919811111111", "type": "text",
           "text": "hello", "timestamp": "1", "name": "Ravi"}
    assert handle_inbound_message(str(tid), msg) == "stored"
    assert handle_inbound_message(str(tid), msg) == "done"
    assert len(calls) == 2 and calls[0] == calls[1] and calls[0][2] == "wamid.ENQ"


def test_full_pipeline_from_inbound_to_sent_reply(wa_tenant, monkeypatch):
    """Inbound message -> stored -> agent -> reply sent, all on the real database."""
    tid, _ = wa_tenant
    queued = []
    monkeypatch.setattr("app.workers.process_message.enqueue_reply", lambda t, c, w: queued.append((t, c, w)))
    handle_inbound_message(str(tid), {"wamid": "wamid.PIPE", "from": "+919811111111", "type": "text",
                                      "text": "Hi, 2BHK in Patia?", "timestamp": "1", "name": "Ravi"})
    sender = RecordingSender()
    t, c, w = queued[0]
    assert handle_reply(t, c, w, llm=ScriptedLLM(say("Sure! What is your budget?")), sender=sender) == "sent"
    assert sender.sent == [("+919811111111", "Sure! What is your budget?")]
