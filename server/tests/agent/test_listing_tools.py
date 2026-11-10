import uuid

import pytest
from sqlalchemy.orm import Session

from app.agent.tools import ToolContext, execute_tool, schemas
from app.agent.tools.check_affordability import max_loan_for_emi
from app.db.models import Listing, ListingMedia, Tenant
from app.db.session import engine_owner
from app.utils.finance import compute_emi


def _ctx(tid):
    return ToolContext(tenant_id=tid, contact_id=uuid.uuid4(), conversation_id=uuid.uuid4())


def _listing(tid, **kw):
    fields = dict(listing_type="sale", project="Lotus Heights", price=5_000_000, bhk=2, area_sqft=1000,
                  location="Patia", furnishing="semi-furnished", status="available",
                  rera_number="ODRERA-TEST-1")
    fields.update(kw)
    with Session(engine_owner) as s:
        r = Listing(tenant_id=tid, **fields)
        s.add(r)
        s.flush()
        lid = r.id
        s.commit()
        return str(lid)


def test_both_tools_are_registered_for_the_agent():
    names = {t["name"] for t in schemas()}
    assert {"get_listing_details", "check_affordability"} <= names


# ---- get_listing_details -------------------------------------------------------------------

def test_details_return_the_real_record_and_photo_count(team_tenant):
    tid, _ = team_tenant
    lid = _listing(tid)
    with Session(engine_owner) as s:
        for i in range(2):
            mid = uuid.uuid4()
            s.add(ListingMedia(id=mid, tenant_id=tid, listing_id=uuid.UUID(lid), filename=f"{i}.png",
                               content_type="image/png", size_bytes=1,
                               storage_key=f"{tid}/{mid}.png", position=i))
        s.commit()

    r = execute_tool("get_listing_details", {"listing_id": lid}, _ctx(tid))

    assert r["project"] == "Lotus Heights" and r["price"] == 5_000_000 and r["bhk"] == 2
    assert r["rera_number"] == "ODRERA-TEST-1" and r["photo_count"] == 2
    assert r["price_per_sqft"] == 5000 and r["not_recorded"] == []


def test_details_say_what_is_not_recorded(team_tenant):
    tid, _ = team_tenant
    lid = _listing(tid, area_sqft=None, furnishing=None, location=None)
    r = execute_tool("get_listing_details", {"listing_id": lid}, _ctx(tid))
    assert set(r["not_recorded"]) == {"area_sqft", "furnishing", "location"}
    assert "price_per_sqft" not in r


def test_details_hide_unpromotable_withdrawn_and_other_companies(team_tenant):
    tid, _ = team_tenant
    no_rera = _listing(tid, rera_number=None)
    blank_rera = _listing(tid, rera_number="  ")
    withdrawn = _listing(tid, status="withdrawn")
    rent_without_rera = _listing(tid, listing_type="rent", rera_number=None, price=15000)
    with Session(engine_owner) as s:
        other = Tenant(name="Other Realty")
        s.add(other)
        s.flush()
        other_id = other.id
        s.commit()
    try:
        theirs = _listing(other_id)
        for bad in (no_rera, blank_rera, withdrawn, theirs):
            assert execute_tool("get_listing_details", {"listing_id": bad}, _ctx(tid)) == {"error": "listing not found"}
        # A rental needs no RERA number, so it is fine.
        assert execute_tool("get_listing_details", {"listing_id": rent_without_rera}, _ctx(tid))["type"] == "rent"
    finally:
        with Session(engine_owner) as s:
            from sqlalchemy import delete
            s.execute(delete(Listing).where(Listing.tenant_id == other_id))
            s.execute(delete(Tenant).where(Tenant.id == other_id))
            s.commit()


def test_details_reject_bad_ids(team_tenant):
    tid, _ = team_tenant
    assert "error" in execute_tool("get_listing_details", {"listing_id": "not-an-id"}, _ctx(tid))
    assert "error" in execute_tool("get_listing_details", {}, _ctx(tid))
    assert execute_tool("get_listing_details", {"listing_id": str(uuid.uuid4())}, _ctx(tid)) == {"error": "listing not found"}


# ---- check_affordability -------------------------------------------------------------------

BUY = {"property_price": 5_000_000, "down_payment_percent": 20, "annual_rate_percent": 8.5, "years": 20}


def test_affordability_verdicts_follow_the_share_of_income(team_tenant):
    tid, _ = team_tenant
    emi = compute_emi(4_000_000, 8.5, 20)["emi"]
    for income, verdict in ((100_000, "comfortable"), (80_000, "stretch"), (60_000, "too_high")):
        r = execute_tool("check_affordability", {**BUY, "monthly_income": income}, _ctx(tid))
        assert r["emi"] == emi and r["loan_amount"] == 4_000_000 and r["down_payment_amount"] == 1_000_000
        assert r["verdict"] == verdict
        assert r["emi_share_of_income_percent"] == round(emi / income * 100, 1)


def test_existing_emis_count_against_the_customer(team_tenant):
    tid, _ = team_tenant
    plain = execute_tool("check_affordability", {**BUY, "monthly_income": 100_000}, _ctx(tid))
    loaded = execute_tool("check_affordability", {**BUY, "monthly_income": 100_000, "existing_monthly_emi": 10_000}, _ctx(tid))
    assert plain["verdict"] == "comfortable" and loaded["verdict"] == "stretch"
    assert loaded["total_monthly_emi"] == loaded["emi"] + 10_000
    assert loaded["max_comfortable_loan"] < plain["max_comfortable_loan"]


def test_max_comfortable_loan_never_exceeds_the_limit():
    for emi in (1, 5_000, 30_000, 123_456):
        loan = max_loan_for_emi(emi, 8.5, 20)
        if loan > 0:
            assert compute_emi(loan, 8.5, 20)["emi"] <= emi + 1  # +1 for rounding
    assert max_loan_for_emi(0, 8.5, 20) == 0 and max_loan_for_emi(-5, 8.5, 20) == 0
    assert max_loan_for_emi(10_000, 0, 10) == 1_200_000


def test_affordability_from_a_listing_and_for_a_rental(team_tenant):
    tid, _ = team_tenant
    sale = _listing(tid)
    r = execute_tool("check_affordability", {"listing_id": sale, "monthly_income": 100_000,
                                             "down_payment_percent": 20, "annual_rate_percent": 8.5, "years": 20}, _ctx(tid))
    assert r["property_price"] == 5_000_000 and r["verdict"] == "comfortable"

    rent = _listing(tid, listing_type="rent", price=15_000, rera_number=None)
    r = execute_tool("check_affordability", {"listing_id": rent, "monthly_income": 60_000, "existing_monthly_emi": 5_000}, _ctx(tid))
    assert r["type"] == "rent" and r["total_monthly_commitment"] == 20_000
    assert r["verdict"] == "stretch" and r["max_comfortable_rent"] == 13_000


def test_affordability_refuses_unavailable_or_hidden_listings(team_tenant):
    tid, _ = team_tenant
    args = {"monthly_income": 100_000, "down_payment_percent": 20, "annual_rate_percent": 8.5, "years": 20}
    sold = _listing(tid, status="sold")
    no_rera = _listing(tid, rera_number=None)
    no_price = _listing(tid, price=None)
    assert "no longer available" in execute_tool("check_affordability", {**args, "listing_id": sold}, _ctx(tid))["error"]
    assert execute_tool("check_affordability", {**args, "listing_id": no_rera}, _ctx(tid)) == {"error": "listing not found"}
    assert "not recorded" in execute_tool("check_affordability", {**args, "listing_id": no_price}, _ctx(tid))["error"]


@pytest.mark.parametrize("args", [
    {},                                                                  # no income
    {"monthly_income": 0, **BUY},                                        # zero income
    {"monthly_income": "lots", **BUY},                                   # not a number
    {"monthly_income": 100_000, "property_price": 5_000_000},            # purchase without loan terms
    {"monthly_income": 100_000, "property_price": 5_000_000, "down_payment_percent": 100, "annual_rate_percent": 8.5, "years": 20},
    {"monthly_income": 100_000, **{**BUY, "years": 40}},                 # tenure out of range
    {"monthly_income": 100_000, **{**BUY, "annual_rate_percent": 50}},   # rate out of range
    {"monthly_income": 100_000, "down_payment_percent": 20, "annual_rate_percent": 8.5, "years": 20},  # no price at all
])
def test_affordability_rejects_bad_input_with_a_readable_error(team_tenant, args):
    tid, _ = team_tenant
    r = execute_tool("check_affordability", args, _ctx(tid))
    assert list(r) == ["error"] and isinstance(r["error"], str)