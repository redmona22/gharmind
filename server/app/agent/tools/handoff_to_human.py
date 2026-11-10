from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.agent.tools.registry import ToolError, tool
from app.db.models import Conversation, Handoff


@tool(
    "handoff_to_human",
    "Pass the conversation to a human team member. Use when the customer wants a person, is upset, or you cannot help. "
    "Give a short summary: budget, preferences, what was shown, any objections.",
    {
        "reason": {"type": "string", "description": "Short code, e.g. customer_request, upset, cannot_help"},
        "summary": {"type": "string"},
    },
    ["reason", "summary"],
)
def handoff_to_human(s, ctx, a: dict) -> dict:
    reason = str(a.get("reason") or "").strip()[:100]
    summary = str(a.get("summary") or "").strip()[:4000]
    if not reason or not summary:
        raise ToolError("reason and summary are required")

    # The unique index on open handoffs makes a repeat call return the existing one.
    created = s.execute(
        pg_insert(Handoff)
        .values(
            tenant_id=ctx.tenant_id,
            conversation_id=ctx.conversation_id,
            reason=reason,
            summary=summary,
        )
        .on_conflict_do_nothing(
            index_elements=["tenant_id", "conversation_id", "reason"],
            index_where=text("resolved = false"),
        )
        .returning(Handoff.id)
    ).scalar_one_or_none()

    if created is None:
        existing = s.execute(
            select(Handoff.id).where(
                Handoff.tenant_id == ctx.tenant_id,
                Handoff.conversation_id == ctx.conversation_id,
                Handoff.reason == reason,
                Handoff.resolved.is_(False),
            )
        ).scalar_one()
        status, handoff_id = "already_open", existing
    else:
        status, handoff_id = "created", created

    conv = s.execute(
        select(Conversation).where(
            Conversation.id == ctx.conversation_id, Conversation.tenant_id == ctx.tenant_id
        )
    ).scalar_one()
    conv.status = "human"  # the agent stops replying; a salesperson takes over
    return {"handoff_id": str(handoff_id), "status": status}
