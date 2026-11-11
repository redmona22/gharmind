"""The Gharmind conversation loop.

run_agent() decides what to do with the latest customer message and returns the reply text.
It does NOT send anything: a later step stores and sends the reply under one idempotency key.
Safety checks (opt-out, handoff, banned claims, number check) are plain code, not prompt text.
So are the lookups: code runs the listing, affordability and EMI tools when the message calls
for them and hands the results to the model as facts, because the small free model rarely
chooses to call tools by itself.
"""
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.agent.extract import extract_lead_facts
from app.agent.fallback import hold_message, opt_out_message
from app.agent.guardrails.banned_claims import find_banned
from app.agent.guardrails.handoff_rules import check_handoff
from app.agent.guardrails.number_check import find_violations, quoted_numbers
from app.agent.guardrails.opt_out import is_opt_out
from app.agent.prefetch import prefetch_context
from app.agent.router import pick_model
from app.agent.tools import ToolContext, execute_tool, schemas
from app.core.tenancy import tenant_session
from app.db.models import AuditLog, Consent, Contact, Conversation, Message, Tenant

log = logging.getLogger(__name__)

PROMPTS = Path(__file__).parent / "prompts"
HISTORY_LIMIT = 12
MAX_TOOL_STEPS = 5
EARLIER_CUSTOMER_MESSAGES = 3  # how many earlier customer messages the lookups may read


@dataclass
class AgentResult:
    reply: str | None
    action: str  # reply | handoff | opt_out | fallback | silent
    handoff_reason: str | None = None
    tools_called: list[str] = field(default_factory=list)


@dataclass
class _Loaded:
    company: str
    contact_id: uuid.UUID
    language: str
    consent: str
    qualification: dict
    conv_status: str
    history: list[tuple[str, str]]  # (sender, content), oldest first


def _load(tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> _Loaded:
    with tenant_session(tenant_id) as s:
        conv = s.execute(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.tenant_id == tenant_id
            )
        ).scalar_one()
        contact = s.execute(
            select(Contact).where(Contact.id == conv.contact_id, Contact.tenant_id == tenant_id)
        ).scalar_one()
        tenant = s.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one()
        rows = s.execute(
            select(Message.sender, Message.content)
            .where(Message.conversation_id == conversation_id, Message.tenant_id == tenant_id)
            .order_by(Message.created_at.desc())
            .limit(HISTORY_LIMIT)
        ).all()
        return _Loaded(
            company=tenant.name,
            contact_id=contact.id,
            language=contact.language or "en",
            consent=contact.consent_status,
            qualification=dict(contact.qualification or {}),
            conv_status=conv.status,
            history=[(r.sender, r.content) for r in reversed(rows)],
        )


def _audit(tenant_id: uuid.UUID, action: str, detail: dict) -> None:
    with tenant_session(tenant_id) as s:
        s.add(AuditLog(tenant_id=tenant_id, actor="agent", action=action, detail=detail))


def _summary(d: _Loaded, reason: str, extra: str = "") -> str:
    lines = [f"Reason: {reason}."]
    if d.qualification:
        lines.append("Lead info: " + json.dumps(d.qualification, ensure_ascii=False))
    lines.append("Recent messages:")
    lines += [f"- {who}: {text[:200]}" for who, text in d.history[-6:]]
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _do_handoff(ctx: ToolContext, d: _Loaded, reason: str, extra: str = "") -> AgentResult:
    out = execute_tool("handoff_to_human", {"reason": reason, "summary": _summary(d, reason, extra)}, ctx)
    if "error" in out:
        log.error("HANDOFF FAILED (%s): %s", reason, out["error"])  # no human was alerted
    return AgentResult(hold_message(d.language), "handoff", handoff_reason=reason)


def _record_opt_out(tenant_id: uuid.UUID, d: _Loaded, text: str) -> None:
    with tenant_session(tenant_id) as s:
        contact = s.execute(
            select(Contact).where(Contact.id == d.contact_id, Contact.tenant_id == tenant_id)
        ).scalar_one()
        contact.consent_status = "opted_out"
        s.add(
            Consent(
                tenant_id=tenant_id, contact_id=d.contact_id,
                channel="whatsapp", action="opt_out", wording=text[:500],
            )
        )
        s.add(AuditLog(
            tenant_id=tenant_id, actor="agent", action="opt_out",
            detail={"text": text[:200], "conversation_status": d.conv_status},
        ))


def _save_facts(ctx: ToolContext, d: _Loaded, text: str) -> bool:
    """Save what the customer just told us, in plain code, so a model that skips the
    save_lead_info tool cannot leave the lead unscored. Never blocks the reply."""
    try:
        facts = extract_lead_facts(text)
        if not facts:
            return False
        out = execute_tool("save_lead_info", facts, ctx)
        if "error" in out:
            log.warning("auto save_lead_info failed: %s", out["error"])
            return False
        d.qualification.update(facts)  # keep this turn's view in step with the database
        return True
    except Exception:
        log.exception("auto save_lead_info crashed")
        return False


def _system_prompt(d: _Loaded) -> str:
    base = (PROMPTS / "base.md").read_text(encoding="utf-8").replace("{company}", d.company)
    sales = (PROMPTS / "sales.md").read_text(encoding="utf-8")
    known = json.dumps(d.qualification, ensure_ascii=False) if d.qualification else "nothing yet"
    return (
        f"{base}\n\n{sales}\n\n"
        f"Today's date: {date.today().isoformat()}\n"
        f"Customer's language preference on file: {d.language}\n"
        f"What we already know about this customer: {known}"
    )


def _facts_block(found: list[tuple[str, dict]]) -> str:
    """The looked-up results, worded as instructions for the model."""
    if not found:
        return ""
    lines = [
        "",
        "Facts our system already looked up for the customer's latest message. They are exact. "
        "Answer from them, quote every number exactly as given, never contradict them and never "
        "add property details that are not here. If a search found nothing, say so honestly. "
        "Never promise that a loan will be approved.",
    ]
    for name, result in found:
        lines.append(f"- {name}: " + json.dumps(result, ensure_ascii=False, default=str))
    return "\n".join(lines)


def _api_messages(history: list[tuple[str, str]]) -> list[dict]:
    out: list[dict] = []
    for sender, content in history:
        role = "user" if sender == "client" else "assistant"
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n" + content
        else:
            out.append({"role": role, "content": content})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def _block_dict(b) -> dict:
    if b.type == "text":
        return {"type": "text", "text": b.text}
    return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}


def _converse(llm, model, system, messages, ctx, tool_texts, tools_called) -> str:
    """Let the model call tools until it produces a final text reply."""
    for _ in range(MAX_TOOL_STEPS):
        resp = llm.create(
            model=model, system=system, messages=messages, tools=schemas(), max_tokens=700
        )
        messages.append({"role": "assistant", "content": [_block_dict(b) for b in resp.content]})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        results = []
        for u in uses:
            out = execute_tool(u.name, u.input, ctx)
            tools_called.append(u.name)
            text = json.dumps(out, ensure_ascii=False, default=str)
            tool_texts.append(text)
            results.append({"type": "tool_result", "tool_use_id": u.id, "content": text})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("too many tool steps")


def _problems(reply: str, sources: list[str]) -> list[str]:
    if not reply:
        return ["the reply was empty"]
    out = []
    if banned := find_banned(reply):
        out.append(f"it contains a claim we must never make: {banned}")
    if bad := find_violations(reply, sources):
        out.append(f"these amounts did not come from a tool result or the customer: {bad}")
    return out


def run_agent(tenant_id: uuid.UUID, conversation_id: uuid.UUID, llm=None) -> AgentResult:
    d = _load(tenant_id, conversation_id)
    ctx = ToolContext(tenant_id, d.contact_id, conversation_id)

    # 1. Nothing to do when messaging has already stopped or there is nothing new to answer.
    if d.consent == "opted_out":
        return AgentResult(None, "silent")
    if not d.history or d.history[-1][0] != "client":
        return AgentResult(None, "silent")  # nothing new to answer

    text = d.history[-1][1]

    # 2. Opt-out ends all messaging immediately. This runs BEFORE the "human is handling it"
    #    check, so a STOP sent while a salesperson has the chat is still recorded.
    if is_opt_out(text):
        _record_opt_out(tenant_id, d, text)
        return AgentResult(opt_out_message(d.language), "opt_out")

    # 3. A human is handling the chat (or it is closed): the agent stays quiet.
    if d.conv_status in ("human", "closed"):
        return AgentResult(None, "silent")

    # 4. Save the facts the customer just stated, in plain code, before anything else
    #    reads the lead profile (the handoff rules and the model both use it).
    auto_saved = _save_facts(ctx, d, text)

    # 5. Handoff triggers are decided in code, before the model sees anything.
    qualified = bool(d.qualification.get("budget_max") or d.qualification.get("budget_min"))
    if reason := check_handoff(text, qualified):
        return _do_handoff(ctx, d, reason)

    # 6. Look things up in code: listing details, affordability, EMI, search.
    earlier = [c for who, c in d.history[:-1] if who == "client"][-EARLIER_CUSTOMER_MESSAGES:]
    found = prefetch_context(ctx, text, earlier, d.qualification)

    # 7. The model, with tools, then the output checks.
    tools_called: list[str] = []
    try:
        if llm is None:
            from app.agent.llm_client import get_llm

            llm = get_llm()

        inbound = sum(1 for who, _ in d.history if who == "client")
        model = pick_model(text, inbound)
        system = _system_prompt(d) + _facts_block(found)
        messages = _api_messages(d.history)
        tool_texts: list[str] = [json.dumps(r, ensure_ascii=False, default=str) for _, r in found]

        reply = _converse(llm, model, system, messages, ctx, tool_texts, tools_called)

        def sources() -> list[str]:
            customer = [c for who, c in d.history if who == "client"]
            return tool_texts + customer + [json.dumps(d.qualification, ensure_ascii=False)]

        problems = _problems(reply, sources())
        if problems:
            _audit(tenant_id, "reply_blocked", {"draft": reply[:1000], "problems": problems})
            messages.append(
                {
                    "role": "user",
                    "content": "[System check] Your draft was blocked: " + "; ".join(problems)
                    + ". Rewrite it. Use only amounts from the facts above or tool results (call the tool "
                    "if you need one), make no promises about returns, and keep it short.",
                }
            )
            reply = _converse(llm, model, system, messages, ctx, tool_texts, tools_called)
            problems = _problems(reply, sources())
            if problems:
                _audit(tenant_id, "reply_blocked", {"draft": reply[:1000], "problems": problems})
                return _do_handoff(ctx, d, "guardrail_blocked", "Blocked draft: " + reply[:300])
    except Exception:
        log.exception("agent failed")
        return _do_handoff(ctx, d, "ai_unavailable")

    _audit(
        tenant_id, "reply_checked",
        {
            "numbers": quoted_numbers(reply), "tools": tools_called, "model": model,
            "auto_saved": auto_saved, "prefetched": [name for name, _ in found],
        },
    )
    return AgentResult(reply, "reply", tools_called=tools_called)