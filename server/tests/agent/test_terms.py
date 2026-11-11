import pytest

from app.agent.terms import extract_finance_terms, find_location, find_mentioned_projects


def test_the_real_conversation_that_the_model_ignored():
    texts = ["My income is 1 lakh per month",
             "can I afford it with 20% down at 8.5% for 20 years?"]
    assert extract_finance_terms(texts) == {
        "monthly_income": 100_000, "down_payment_percent": 20.0,
        "annual_rate_percent": 8.5, "years": 20,
    }


@pytest.mark.parametrize("text,expected", [
    ("I earn 75,000 a month", {"monthly_income": 75_000}),
    ("my salary is 1.2 lakh", {"monthly_income": 120_000}),
    ("income 80k per month", {"monthly_income": 80_000}),
    ("take home 2 lakhs", {"monthly_income": 200_000}),
    ("my income is 2", {}),                                   # too small to be a monthly income
    ("I have existing EMI of 10k and income 1 lakh", {"existing_monthly_emi": 10_000, "monthly_income": 100_000}),
    ("20% down payment", {"down_payment_percent": 20.0}),
    ("down payment of 25%", {"down_payment_percent": 25.0}),
    ("interest rate is 9%", {"annual_rate_percent": 9.0}),
    ("9.25% interest for 15 yrs", {"annual_rate_percent": 9.25, "years": 15}),
    ("a 25 year loan", {"years": 25}),
    ("I am 30 years old", {}),                                # an age is not a loan tenure
    ("tenure 40 years", {}),                                  # out of range
    ("hello", {}),
])
def test_single_messages(text, expected):
    assert extract_finance_terms([text]) == expected


def test_newer_message_overrides_older():
    out = extract_finance_terms(["at 8.5% for 20 years", "make it at 9%"])
    assert out == {"annual_rate_percent": 9.0, "years": 20}


LISTINGS = [("1", "Lotus Heights"), ("2", "Sunrise Heights (demo)"), ("3", "Test Tower"), ("4", "Sunrise Residency")]


@pytest.mark.parametrize("text,expected", [
    ("Tell me more about Lotus Heights", ["1"]),
    ("LOTUS   heights!!", ["1"]),
    ("what about sunrise heights?", ["2"]),
    ("sunrise residency or lotus heights", ["1", "4"]),
    ("heights", []),
    ("I want a flat", []),
])
def test_find_mentioned_projects(text, expected):
    assert sorted(find_mentioned_projects(text, LISTINGS)) == expected


def test_find_location_uses_the_companys_own_areas():
    places = ["Patia, Bhubaneswar", "Nayapalli", None, "Khandagiri, Bhubaneswar"]
    assert find_location("Hi, I want a 2 BHK to buy in Patia", places) == "patia"
    assert find_location("anything near khandagiri?", places) == "khandagiri"
    assert find_location("something in Bhubaneswar", places) is None  # only the first part counts
    assert find_location("hello", places) is None