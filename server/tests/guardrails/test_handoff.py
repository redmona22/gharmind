from app.agent.guardrails.handoff_rules import check_handoff


def test_price_negotiation():
    assert check_handoff("Can you give a discount?", False) == "price_negotiation"
    assert check_handoff("what is the final price", False) == "price_negotiation"
    assert check_handoff("thoda kam karo", False) == "price_negotiation"


def test_legal_and_complaints():
    assert check_handoff("I want to take legal advice", False) == "legal_or_complaint"
    assert check_handoff("this is a fraud", False) == "legal_or_complaint"


def test_visit_request():
    assert check_handoff("can I visit tomorrow", False) == "visit_request"
    assert check_handoff("I want to book a site visit", False) == "visit_request"


def test_minor():
    assert check_handoff("I'm 16", False) == "minor"
    assert check_handoff("I'm 26", False) is None


def test_interest_needs_a_budget_first():
    assert check_handoff("I'm interested in 2BHK flats", False) is None
    assert check_handoff("I'm interested in 2BHK flats", True) == "buying_intent"
    assert check_handoff("Hi, 2BHK in Patia?", True) is None
