from datetime import date

from app.agent.guardrails.number_check import find_violations, quoted_numbers

TOOL = ['{"price": 4500000, "project": "Sunrise Heights", "id": "3f2a1b2c-1111-2222-3333-444455556666", "bhk": 2}']


def fv(reply, src=TOOL):
    return find_violations(reply, src)


def test_price_matching_tool_result_passes_in_every_indian_format():
    assert fv("Sunrise Heights, 2BHK at ₹45 lakh.") == []
    assert fv("Sunrise Heights, 2BHK at ₹45,00,000.") == []
    assert fv("Sunrise Heights at Rs 4500000") == []
    assert fv("It is 45L") == []


def test_invented_price_is_blocked():
    assert fv("It is only ₹39 lakh!") == ["₹39 lakh"]
    assert fv("only 39L") != []
    assert fv("It is 3,900,000") != []


def test_small_plain_numbers_are_not_checked():
    assert fv("2 BHK, 3 options, floor 4, 5 km away") == []


def test_area_is_checked_even_when_glued_to_text():
    assert fv("2000sqft") != []
    assert fv("2,000 sq ft") != []


def test_emi_rounding_allowed_but_not_a_different_number():
    assert fv("about ₹38,000 a month", ['{"emi": 37962}']) == []
    assert fv("about ₹39,000 a month", ['{"emi": 37962}']) != []


def test_customers_own_numbers_can_be_repeated():
    assert fv("Your 50 lakh budget is fine", ["my budget is 50 lakh"]) == []


def test_current_year_and_phone_numbers_are_ignored():
    assert fv(f"Visit in {date.today().year}") == []
    assert fv("call 9811111111") == []


def test_quoted_numbers_listed_for_audit():
    assert "₹45 lakh" in quoted_numbers("at ₹45 lakh in Patia")
