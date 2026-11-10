import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.fallback import hold_message
from app.agent.loop import run_agent
from app.agent.tools import ToolContext, execute_tool
from app.db.models import Contact, Conversation, Listing, Message
from app.db.session import engine_owner
from tests.agent.fakes import BrokenLLM, ScriptedLLM, call, say
from tests.helpers import count


def seed(tid, message, qualification=None, language="en"):
    with Session(engine_owner) as s:
        c = Contact(
            tenant_id=tid, phone=f"+9199{uuid.uuid4().int % 10**8:08d}",
            language=language, qualification=qualification or {},
        )
        s.add(c)
        s.flush()
        conv = Conversation(tenant_id=tid, contact_id=c.id)
        s.add(conv)
        s.flush()
        s.add(Message(
            tenant_id=tid, conversation_id=conv.id, direction="in", sender="client",
            content=message, wamid=f"w-{uuid.uuid4()}",
        ))
        s.commit()
        return c.id, conv.id


def seed_listings(tid):
    with Session(engine_owner) as s:
        s.add_all([
            Listing(tenant_id=tid, listing_type="sale", project="Sunrise Heights", price=4_500_000,
                    bhk=2, area_sqft=1050, location="Patia, Bhubaneswar", rera_number="RP/19/2020/123"),
            Listing(tenant_id=tid, listing_type="sale", project="Hidden Towers", price=3_900_000,
                    bhk=2, location="Patia, Bhubaneswar", rera_number=None),
            Listing(tenant_id=tid, listing_type="rent", project="Green Nest", price=18_000,
                    bhk=2, location="Patia, Bhubaneswar"),
        ])
        s.commit()


def db_scalar(sql, **params):
    with engine_owner.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def test_reply_with_real_price_passes(wa_tenant):
    tid, _ = wa_tenant
    seed_listings(tid)
    _, conv = seed(tid, "Looking for a 2BHK in Patia")
    llm = ScriptedLLM(call("search_listings", location="Patia", listing_type="sale"),
                      say("Sunrise Heights in Patia is a 2BHK at ₹45 lakh. Want to see more options?"))
    r = run_agent(tid, conv, llm)
    assert r.action == "reply" and "45 lakh" in r.reply
    assert r.tools_called == ["search_listings"]


def test_invented_price_is_blocked_and_handed_off(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "hi")
    llm = ScriptedLLM(say("It is only ₹39 lakh!"))
    r = run_agent(tid, conv, llm)
    assert r.action == "handoff" and r.handoff_reason == "guardrail_blocked"
    assert r.reply == hold_message("en")
    assert llm.calls == 2  # first draft, then one rewrite attempt
    assert db_scalar("SELECT status FROM conversations WHERE id = :c", c=conv) == "human"
    with engine_owner.connect() as conn:
        assert count(conn, "handoffs", tid) == 1


def test_banned_claim_is_blocked(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "is it a good buy?")
    r = run_agent(tid, conv, ScriptedLLM(say("This is the best investment with guaranteed returns.")))
    assert r.action == "handoff" and r.handoff_reason == "guardrail_blocked"


def test_rewrite_after_a_block_can_succeed(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "hi")
    llm = ScriptedLLM(say("Only ₹39 lakh!"), say("Happy to help. What is your budget?"))
    r = run_agent(tid, conv, llm)
    assert r.action == "reply" and llm.calls == 2


def test_discount_request_hands_off_without_calling_the_model(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "Can you give me a discount?")
    llm = BrokenLLM()
    r = run_agent(tid, conv, llm)
    assert r.action == "handoff" and r.handoff_reason == "price_negotiation"
    assert llm.calls == 0
    with engine_owner.connect() as conn:
        assert count(conn, "handoffs", tid) == 1


def test_visit_request_hands_off(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "Can I visit the flat tomorrow?")
    assert run_agent(tid, conv, BrokenLLM()).handoff_reason == "visit_request"


def test_interested_only_hands_off_after_a_budget_is_known(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "I'm interested in 2BHK flats")
    assert run_agent(tid, conv, ScriptedLLM(say("Great! What is your budget?"))).action == "reply"
    _, conv2 = seed(tid, "I'm interested in 2BHK flats", {"budget_max": 6_000_000})
    assert run_agent(tid, conv2, BrokenLLM()).handoff_reason == "buying_intent"


def test_ai_down_sends_holding_message_and_alerts_a_human(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "Hello")
    r = run_agent(tid, conv, BrokenLLM())
    assert r.action == "handoff" and r.handoff_reason == "ai_unavailable"
    assert r.reply == hold_message("en")
    with engine_owner.connect() as conn:
        assert count(conn, "handoffs", tid) == 1


def test_holding_message_follows_customer_language(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "discount milega?", language="hi")
    assert run_agent(tid, conv, BrokenLLM()).reply == hold_message("hi")


def test_opt_out_ends_all_messaging(wa_tenant):
    tid, _ = wa_tenant
    contact, conv = seed(tid, "STOP")
    r = run_agent(tid, conv, BrokenLLM())
    assert r.action == "opt_out"
    assert db_scalar("SELECT consent_status FROM contacts WHERE id = :c", c=contact) == "opted_out"
    with engine_owner.connect() as conn:
        assert count(conn, "consents", tid) == 1
    assert run_agent(tid, conv, BrokenLLM()).action == "silent"  # never answers again


def test_agent_stays_silent_when_a_human_has_taken_over(wa_tenant):
    tid, _ = wa_tenant
    _, conv = seed(tid, "hello?")
    with engine_owner.begin() as c:
        c.execute(text("UPDATE conversations SET status = 'human' WHERE id = :c"), {"c": conv})
    llm = BrokenLLM()
    assert run_agent(tid, conv, llm).action == "silent" and llm.calls == 0


def test_handoff_tool_is_idempotent(wa_tenant):
    tid, _ = wa_tenant
    contact, conv = seed(tid, "hello")
    ctx = ToolContext(tid, contact, conv)
    args = {"reason": "customer_request", "summary": "wants a call"}
    first = execute_tool("handoff_to_human", args, ctx)
    second = execute_tool("handoff_to_human", args, ctx)
    assert first["status"] == "created" and second["status"] == "already_open"
    assert first["handoff_id"] == second["handoff_id"]
    with engine_owner.connect() as conn:
        assert count(conn, "handoffs", tid) == 1


def test_rera_block_hides_sale_listings_without_a_rera_number(wa_tenant):
    tid, _ = wa_tenant
    seed_listings(tid)
    contact, conv = seed(tid, "hi")
    out = execute_tool("search_listings", {}, ToolContext(tid, contact, conv))
    assert {x["project"] for x in out["listings"]} == {"Sunrise Heights", "Green Nest"}


def test_save_lead_info_updates_profile_and_score(wa_tenant):
    tid, _ = wa_tenant
    contact, conv = seed(tid, "hi")
    out = execute_tool(
        "save_lead_info",
        {"name": "Ravi", "budget_max": 6_000_000, "location_pref": "Patia", "bhk": 2,
         "purpose": "buy", "timeline": "this month", "financing": "loan"},
        ToolContext(tid, contact, conv),
    )
    assert out == {"saved": True, "lead_score": 100}
    assert db_scalar("SELECT name FROM contacts WHERE id = :c", c=contact) == "Ravi"
    assert db_scalar("SELECT (qualification->>'budget_max')::int FROM contacts WHERE id = :c", c=contact) == 6_000_000


def test_calculate_emi_tool_returns_exact_numbers(wa_tenant):
    tid, _ = wa_tenant
    contact, conv = seed(tid, "hi")
    out = execute_tool(
        "calculate_emi",
        {"property_price": 5_000_000, "down_payment_percent": 20, "annual_rate_percent": 8.5, "years": 20},
        ToolContext(tid, contact, conv),
    )
    assert out["down_payment_amount"] == 1_000_000 and out["loan_amount"] == 4_000_000
    assert out["emi"] == 34713
