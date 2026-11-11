import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.loop import run_agent
from app.agent.prefetch import prefetch_context
from app.agent.tools import ToolContext
from app.db.models import Contact, Conversation, Listing, Message
from app.db.session import engine_owner


def _ctx(tid):
    return ToolContext(tenant_id=tid, contact_id=uuid.uuid4(), conversation_id=uuid.uuid4())


def _listing(tid, **kw):
    fields = dict(listing_type="sale", project="Lotus Heights", price=5_000_000, bhk=2, area_sqft=1000,
                  location="Patia, Bhubaneswar", furnishing="semi-furnished", status="available",
                  rera_number="ODRERA-TEST-1")
    fields.update(kw)
    with Session(engine_owner) as s:
        r = Listing(tenant_id=tid, **fields)
        s.add(r)
        s.flush()
        lid = r.id
        s.commit()
        return str(lid)


def _names(found):
    return [name for name, _ in found]


def _chat(tid, texts, status="agent", consent="unknown"):
    """A conversation whose customer messages are `texts` (oldest first). Returns (conversation id, contact id)."""
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    with Session(engine_owner) as s:
        c = Contact(tenant_id=tid, phone=f"+9197{uuid.uuid4().int % 10**8:08d}", consent_status=consent)
        s.add(c)
        s.flush()
        conv = Conversation(tenant_id=tid, contact_id=c.id, channel="whatsapp", status=status)
        s.add(conv)
        s.flush()
        for i, t in enumerate(texts):
            s.add(Message(tenant_id=tid, conversation_id=conv.id, direction="in", sender="client",
                          content=t, created_at=base + timedelta(seconds=i)))
        conv_id, contact_id = conv.id, c.id
        s.commit()
        return conv_id, contact_id


class _FakeLLM:
    """Records the system prompt it was given and answers with a short, harmless reply."""
    def __init__(self):
        self.systems = []
        self.sent = []

    def create(self, model, system, messages, tools, max_tokens):
        self.systems.append(system)
        self.sent.append(json.dumps(messages, ensure_ascii=False))
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Thanks, noted.")])


# ---- prefetch_context ----------------------------------------------------------------------

def test_project_details_are_fetched_when_the_customer_names_it(team_tenant):
    tid, _ = team_tenant
    _listing(tid)
    found = prefetch_context(_ctx(tid), "Tell me more about Lotus Heights", [], {})
    assert _names(found) == ["get_listing_details"]
    assert found[0][1]["project"] == "Lotus Heights" and found[0][1]["price"] == 5_000_000


def test_the_real_conversation_gets_an_exact_affordability_answer(team_tenant):
    tid, _ = team_tenant
    _listing(tid)
    earlier = ["My income is 1 lakh per month", "Tell me more about Lotus Heights"]
    found = prefetch_context(_ctx(tid), "can I afford it with 20% down at 8.5% for 20 years?", earlier, {})
    assert _names(found) == ["get_listing_details", "check_affordability"]
    verdict = dict(found)["check_affordability"]
    assert verdict["emi"] == 34_713 and verdict["verdict"] == "comfortable"


def test_affordability_waits_until_the_loan_terms_are_known(team_tenant):
    tid, _ = team_tenant
    _listing(tid)
    found = prefetch_context(_ctx(tid), "My income is 1 lakh, can I afford Lotus Heights?", [], {})
    assert _names(found) == ["get_listing_details"]  # the model will ask for down payment, rate, years


def test_emi_question_without_income_uses_calculate_emi(team_tenant):
    tid, _ = team_tenant
    _listing(tid)
    found = prefetch_context(_ctx(tid), "Lotus Heights EMI with 20% down at 8.5% for 20 years?", [], {})
    assert _names(found) == ["get_listing_details", "calculate_emi"]
    assert dict(found)["calculate_emi"]["emi"] == 34_713


def test_search_runs_for_bhk_purpose_and_area(team_tenant):
    tid, _ = team_tenant
    _listing(tid)
    _listing(tid, project="Other Tower", bhk=3, location="Nayapalli")
    found = prefetch_context(_ctx(tid), "Hi, I want a 2 BHK to buy in Patia", [], {})
    assert _names(found) == ["search_listings"]
    result = found[0][1]
    assert result["count"] == 1 and result["listings"][0]["project"] == "Lotus Heights"


def test_nothing_runs_for_small_talk_or_hidden_listings(team_tenant):
    tid, _ = team_tenant
    _listing(tid, project="Secret Towers", rera_number=None)
    _listing(tid, project="Gone Heights", status="withdrawn")
    assert prefetch_context(_ctx(tid), "ok thanks", [], {}) == []
    assert prefetch_context(_ctx(tid), "tell me about Secret Towers", [], {}) == []
    assert prefetch_context(_ctx(tid), "tell me about Gone Heights", [], {}) == []


# ---- run_agent: facts reach the model; STOP is always honoured -----------------------------

def test_looked_up_facts_are_given_to_the_model(team_tenant):
    tid, _ = team_tenant
    _listing(tid)
    conv_id, _ = _chat(tid, ["Tell me more about Lotus Heights"])
    llm = _FakeLLM()

    result = run_agent(tid, conv_id, llm=llm)

    assert result.action == "reply" and result.reply == "Thanks, noted."
    assert "get_listing_details" in llm.sent[0] and "ODRERA-TEST-1" in llm.sent[0]


def test_stop_is_recorded_even_while_a_human_is_handling_the_chat(team_tenant):
    tid, _ = team_tenant
    conv_id, contact_id = _chat(tid, ["STOP"], status="human")

    result = run_agent(tid, conv_id, llm=_FakeLLM())

    assert result.action == "opt_out"
    with Session(engine_owner) as s:
        assert s.execute(select(Contact.consent_status).where(Contact.id == contact_id)).scalar_one() == "opted_out"


def test_a_human_handled_chat_stays_silent_for_normal_messages(team_tenant):
    tid, _ = team_tenant
    conv_id, _ = _chat(tid, ["what is the price?"], status="human")
    assert run_agent(tid, conv_id, llm=_FakeLLM()).action == "silent"


def test_an_opted_out_customer_gets_no_reply(team_tenant):
    tid, _ = team_tenant
    conv_id, _ = _chat(tid, ["hello again"], consent="opted_out")
    assert run_agent(tid, conv_id, llm=_FakeLLM()).action == "silent"

def test_a_new_search_beats_a_project_mentioned_earlier(team_tenant):
    tid, _ = team_tenant
    _listing(tid)
    found = prefetch_context(_ctx(tid), "Hi, I want a 2 BHK to buy in Patia", ["Tell me more about Lotus Heights"], {})
    assert _names(found) == ["search_listings"]


def test_a_follow_up_still_uses_the_project_mentioned_earlier(team_tenant):
    tid, _ = team_tenant
    _listing(tid)
    found = prefetch_context(_ctx(tid), "what is the price?", ["Tell me more about Lotus Heights"], {})
    assert _names(found) == ["get_listing_details"]