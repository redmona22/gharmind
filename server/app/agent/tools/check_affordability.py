from app.agent.tools._common import load_listing
from app.agent.tools.registry import ToolError, tool
from app.utils.finance import compute_emi

# Share of monthly income that all loan EMIs (new + existing) may take.
# Banks commonly cap this around 40 to 50 percent. These are product choices; change here.
COMFORTABLE_SHARE = 0.40
STRETCH_SHARE = 0.50
# For rentals: rent plus existing EMIs as a share of income.
RENT_COMFORTABLE_SHARE = 0.30
RENT_STRETCH_SHARE = 0.40

NOTE = "Indicative only. This is not a loan approval or an offer; the bank decides."


def _num(a: dict, key: str, low: float, high: float, default: float | None = None) -> float:
    raw = a.get(key)
    if raw in (None, ""):
        if default is not None:
            return default
        raise ToolError(f"{key} is required")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ToolError(f"{key} must be a number")
    if not (low <= value <= high):
        raise ToolError(f"{key} must be between {low:g} and {high:g}")
    return value


def _verdict(share: float, comfortable: float, stretch: float) -> str:
    if share <= comfortable:
        return "comfortable"
    if share <= stretch:
        return "stretch"
    return "too_high"


def max_loan_for_emi(emi: float, annual_rate_percent: float, years: float) -> int:
    """The largest loan whose EMI is at most `emi` (the reverse of compute_emi)."""
    if emi <= 0:
        return 0
    n = round(years * 12)
    r = annual_rate_percent / 12 / 100
    if r == 0:
        return round(emi * n)
    return round(emi * ((1 + r) ** n - 1) / (r * (1 + r) ** n))


def assess_purchase(income: float, existing_emi: float, price: float, down_payment_percent: float,
                    annual_rate_percent: float, years: float) -> dict:
    down = round(price * down_payment_percent / 100)
    loan = price - down
    if loan <= 0:
        raise ToolError("down payment covers the whole price, no loan is needed")
    loan_info = compute_emi(loan, annual_rate_percent, years)
    total_emi = loan_info["emi"] + existing_emi
    share = total_emi / income
    room = max(0.0, COMFORTABLE_SHARE * income - existing_emi)
    max_loan = max_loan_for_emi(room, annual_rate_percent, years)
    keep = 1 - down_payment_percent / 100
    return {
        "type": "sale",
        "property_price": round(price),
        "down_payment_percent": down_payment_percent,
        "down_payment_amount": down,
        "loan_amount": loan_info["loan_amount"],
        "annual_rate_percent": annual_rate_percent,
        "tenure_years": years,
        "emi": loan_info["emi"],
        "existing_monthly_emi": round(existing_emi),
        "total_monthly_emi": round(total_emi),
        "monthly_income": round(income),
        "emi_share_of_income_percent": round(share * 100, 1),
        "verdict": _verdict(share, COMFORTABLE_SHARE, STRETCH_SHARE),
        "comfortable_limit_percent": round(COMFORTABLE_SHARE * 100),
        "max_comfortable_loan": max_loan,
        "max_comfortable_property_price": round(max_loan / keep) if keep > 0 else None,
        "note": NOTE,
    }


def assess_rent(income: float, existing_emi: float, rent: float) -> dict:
    total = rent + existing_emi
    share = total / income
    return {
        "type": "rent",
        "monthly_rent": round(rent),
        "existing_monthly_emi": round(existing_emi),
        "total_monthly_commitment": round(total),
        "monthly_income": round(income),
        "share_of_income_percent": round(share * 100, 1),
        "verdict": _verdict(share, RENT_COMFORTABLE_SHARE, RENT_STRETCH_SHARE),
        "comfortable_limit_percent": round(RENT_COMFORTABLE_SHARE * 100),
        "max_comfortable_rent": max(0, round(RENT_COMFORTABLE_SHARE * income - existing_emi)),
        "note": "Indicative only. A landlord may ask for more proof of income.",
    }


@tool(
    "check_affordability",
    "Check whether a property is affordable for the customer. Use this when they give their "
    "monthly income and ask if they can afford something. Give listing_id (from search_listings) "
    "or property_price. For a purchase also give down_payment_percent, annual_rate_percent and "
    "years: use only values the customer stated, and if they gave none, ask. Quote its numbers "
    "exactly. Never promise that a loan will be approved.",
    {
        "monthly_income": {"type": "number", "description": "Customer's monthly income in rupees"},
        "existing_monthly_emi": {"type": "number", "description": "Loan EMIs they already pay each month (0 if none)"},
        "listing_id": {"type": "string", "description": "A listing id from search_listings"},
        "property_price": {"type": "number", "description": "Price in rupees, when there is no listing_id"},
        "down_payment_percent": {"type": "number", "description": "Down payment as a percent of price"},
        "annual_rate_percent": {"type": "number", "description": "Yearly interest rate, e.g. 8.5"},
        "years": {"type": "number", "description": "Loan tenure in years (1-30)"},
    },
    ["monthly_income"],
)
def check_affordability(s, ctx, a: dict) -> dict:
    income = _num(a, "monthly_income", 1, 10_000_000_000)
    existing = _num(a, "existing_monthly_emi", 0, 10_000_000_000, default=0.0)

    listing_type = "sale"
    if a.get("listing_id") not in (None, ""):
        listing = load_listing(s, ctx, a["listing_id"])
        if listing.status != "available":
            raise ToolError(f"this property is {listing.status}, so it is no longer available")
        if listing.price is None:
            raise ToolError("the price of this property is not recorded, check with the team")
        price = float(listing.price)
        listing_type = listing.listing_type
    else:
        price = _num(a, "property_price", 1, 10_000_000_000)

    if listing_type == "rent":
        return assess_rent(income, existing, price)

    dp = _num(a, "down_payment_percent", 0, 99.99)
    rate = _num(a, "annual_rate_percent", 0, 30)
    years = _num(a, "years", 1, 30)
    return assess_purchase(income, existing, price, dp, rate, years)