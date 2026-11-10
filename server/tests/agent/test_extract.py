import pytest

from app.agent.extract import extract_lead_facts


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I want a 2 BHK flat in Bhubaneswar, budget 60 lakh", {"budget_max": 6_000_000, "bhk": 2}),
        ("budget is 1.2 crore", {"budget_max": 12_000_000}),
        ("looking for 3bhk under 85 lacs", {"budget_max": 8_500_000, "bhk": 3}),
        ("my budget is 50-60 lakh", {"budget_min": 5_000_000, "budget_max": 6_000_000}),
        ("between 50 lakh to 1 crore", {"budget_min": 5_000_000, "budget_max": 10_000_000}),
        ("2 bhk on rent, around 15k a month", {"budget_max": 15_000, "bhk": 2, "purpose": "rent"}),
        ("budget \u20b965,00,000", {"budget_max": 6_500_000}),
        ("Rs 18000 per month", {"budget_max": 18_000}),
        ("I want to buy a flat", {"purpose": "buy"}),
        ("looking to invest in property", {"purpose": "invest"}),
        ("I will pay all cash", {"financing": "cash"}),
        ("I need a home loan", {"financing": "loan"}),
        ("no loan needed", {"financing": "cash"}),
        ("I want to move in within 2 months", {"timeline": "within 2 months"}),
        ("need it asap", {"timeline": "asap"}),
    ],
)
def test_extracts(text, expected):
    assert extract_lead_facts(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "hi",
        "Can I get a discount?",
        "give me 50 percent discount",
        "my salary is 1 lakh per month",
        "I can pay 10 lakh as down payment",
        "what is the EMI for a 50 lakh loan",
        "deposit of 90000",
        "I want to buy or rent",
        "call me at 9914672453",
        "",
    ],
)
def test_ignores(text):
    got = extract_lead_facts(text)
    assert "budget_max" not in got and "budget_min" not in got