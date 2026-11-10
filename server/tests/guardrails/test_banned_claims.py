from app.agent.guardrails.banned_claims import find_banned


def test_banned_claims_caught():
    for bad in ["guaranteed returns", "This is the best investment", "risk-free",
                "prices will definitely go up", "100% safe", "double your money"]:
        assert find_banned(bad), bad


def test_normal_replies_pass():
    for ok in ["Happy to help", "RERA registered project", "2BHK near the park"]:
        assert not find_banned(ok), ok
