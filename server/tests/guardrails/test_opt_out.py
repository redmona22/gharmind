from app.agent.guardrails.opt_out import is_opt_out


def test_opt_out_words():
    for t in ["STOP", "stop.", " Unsubscribe ", "opt out", "Stop messages!"]:
        assert is_opt_out(t), t


def test_not_opt_out():
    for t in ["don't stop", "stop calling me at night please", "bus stop near the flat"]:
        assert not is_opt_out(t), t
