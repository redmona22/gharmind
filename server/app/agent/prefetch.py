"""Run the lookups in code, so a small model that never calls tools still answers from real data.

Before the model writes a reply, this reads the customer's latest message (and the few before
it) and runs get_listing_details, check_affordability, calculate_emi or search_listings when the
message clearly calls for them. The results are handed to the model as facts. The tools
themselves still enforce every rule (company isolation, RERA, withdrawn listings).
"""
import logging
import re

from sqlalchemy import select

from app.agent.extract import extract_lead_facts
from app.agent.terms import extract_finance_terms, find_location, find_mentioned_projects
from app.agent.tools import ToolContext, execute_tool
from app.core.tenancy import tenant_session
from app.db.models import Listing

log = logging.getLogger(__name__)

MAX_PROJECTS = 2
_FINANCE_INTENT = re.compile(
    r"\b(afford|emi|loan|income|salary|eligible|eligibility|down\s*payment|budget)\b", re.I
)
_EMI_WORD = re.compile(r"\bemi\b", re.I)
_LOAN_TERMS = ("down_payment_percent", "annual_rate_percent", "years")


def _tenant_listings(ctx: ToolContext) -> list[tuple[str, str, str | None]]:
    with tenant_session(ctx.tenant_id) as s:
        rows = s.execute(
            select(Listing.id, Listing.project, Listing.location)
            .where(Listing.tenant_id == ctx.tenant_id, Listing.status != "withdrawn")
            .limit(300)
        ).all()
    return [(str(r.id), r.project, r.location) for r in rows]


def prefetch_context(ctx: ToolContext, text: str, earlier_customer_texts: list[str],
                     qualification: dict) -> list[tuple[str, dict]]:
    """[(tool name, result)] for the lookups this message calls for. Never raises."""
    found: list[tuple[str, dict]] = []
    try:
        listings = _tenant_listings(ctx)
        recent = list(earlier_customer_texts) + [text]

        # Which project is the customer talking about? This message first, then the ones before.
        project_ids: list[str] = []
        for msg in reversed(recent):
            project_ids = find_mentioned_projects(msg, [(i, p) for i, p, _ in listings])
            if project_ids:
                break

        details: list[dict] = []
        for listing_id in project_ids[:MAX_PROJECTS]:
            out = execute_tool("get_listing_details", {"listing_id": listing_id}, ctx)
            if "error" not in out:
                details.append(out)
                found.append(("get_listing_details", out))

        first = details[0] if details else None
        terms = extract_finance_terms(recent)
        asks_about_money = bool(_FINANCE_INTENT.search(text))
        ran_affordability = False

        if first and asks_about_money and terms.get("monthly_income"):
            args: dict | None = {"listing_id": first["id"], "monthly_income": terms["monthly_income"]}
            if terms.get("existing_monthly_emi"):
                args["existing_monthly_emi"] = terms["existing_monthly_emi"]
            if first["type"] == "sale":
                if all(k in terms for k in _LOAN_TERMS):
                    args.update({k: terms[k] for k in _LOAN_TERMS})
                else:
                    args = None  # not enough loan terms yet: the model will ask the customer
            if args:
                out = execute_tool("check_affordability", args, ctx)
                if "error" not in out:
                    found.append(("check_affordability", out))
                    ran_affordability = True

        if (first and first["type"] == "sale" and first.get("price") and not ran_affordability
                and _EMI_WORD.search(text) and all(k in terms for k in _LOAN_TERMS)):
            out = execute_tool(
                "calculate_emi",
                {"property_price": first["price"], **{k: terms[k] for k in _LOAN_TERMS}},
                ctx,
            )
            if "error" not in out:
                found.append(("calculate_emi", out))

        if not details:
            facts = extract_lead_facts(text)
            location = find_location(text, [loc for _, _, loc in listings])
            if facts.get("bhk") or facts.get("budget_max") or location:
                purpose = facts.get("purpose") or qualification.get("purpose")
                args = {
                    "listing_type": {"buy": "sale", "invest": "sale", "rent": "rent"}.get(purpose),
                    "bhk": facts.get("bhk") or qualification.get("bhk"),
                    "max_price": facts.get("budget_max") or qualification.get("budget_max"),
                    "location": location,
                }
                out = execute_tool("search_listings", {k: v for k, v in args.items() if v}, ctx)
                if "error" not in out:
                    found.append(("search_listings", out))
    except Exception:
        log.exception("prefetch failed")  # the reply still goes ahead without these facts
    return found