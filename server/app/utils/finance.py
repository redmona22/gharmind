class ToolError(Exception):
    """A problem with tool input that the agent can read and fix."""


def compute_emi(loan_amount: float, annual_rate_percent: float, years: float) -> dict:
    if loan_amount <= 0:
        raise ToolError("loan_amount must be positive")
    if not (0 <= annual_rate_percent <= 30):
        raise ToolError("annual_rate_percent must be between 0 and 30")
    if not (1 <= years <= 30):
        raise ToolError("years must be between 1 and 30")
    n = round(years * 12)
    r = annual_rate_percent / 12 / 100
    emi = loan_amount / n if r == 0 else loan_amount * r * (1 + r) ** n / ((1 + r) ** n - 1)
    total = emi * n
    return {
        "loan_amount": round(loan_amount),
        "annual_rate_percent": annual_rate_percent,
        "tenure_months": n,
        "emi": round(emi),
        "total_payable": round(total),
        "total_interest": round(total - loan_amount),
    }
