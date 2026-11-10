from app.agent.tools.registry import ToolError, tool
from app.utils.finance import compute_emi


@tool(
    "calculate_emi",
    "Calculate home loan EMI. Give either loan_amount, or property_price with down_payment_percent. "
    "Always use this for any EMI, loan or down payment figure and quote its numbers exactly.",
    {
        "loan_amount": {"type": "number", "description": "Loan amount in rupees"},
        "property_price": {"type": "number", "description": "Property price in rupees"},
        "down_payment_percent": {"type": "number", "description": "Down payment as a percent of price"},
        "annual_rate_percent": {"type": "number", "description": "Yearly interest rate, e.g. 8.5"},
        "years": {"type": "number", "description": "Loan tenure in years (1-30)"},
    },
    ["annual_rate_percent", "years"],
)
def calculate_emi(s, ctx, a: dict) -> dict:
    try:
        rate = float(a["annual_rate_percent"])
        years = float(a["years"])
        extra: dict = {}
        if a.get("property_price") is not None:
            price = float(a["property_price"])
            if a.get("down_payment_percent") is None:
                raise ToolError("down_payment_percent is required with property_price")
            dp = float(a["down_payment_percent"])
            if not (0 <= dp < 100):
                raise ToolError("down_payment_percent must be between 0 and 100")
            down = round(price * dp / 100)
            loan = price - down
            extra = {"property_price": round(price), "down_payment_amount": down}
        elif a.get("loan_amount") is not None:
            loan = float(a["loan_amount"])
        else:
            raise ToolError("give loan_amount, or property_price with down_payment_percent")
    except (KeyError, TypeError, ValueError):
        raise ToolError("annual_rate_percent, years and amounts must be numbers")
    return {**extra, **compute_emi(loan, rate, years)}
