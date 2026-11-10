import pytest

from app.agent.scoring import compute_score
from app.utils.finance import ToolError, compute_emi


def test_emi_known_value():
    r = compute_emi(4_000_000, 8.5, 20)
    assert r["emi"] == 34713 and r["tenure_months"] == 240


def test_zero_interest():
    assert compute_emi(120_000, 0, 1)["emi"] == 10_000


@pytest.mark.parametrize("args", [(0, 8, 10), (1e6, 40, 10), (1e6, 8, 0)])
def test_bad_emi_input_rejected(args):
    with pytest.raises(ToolError):
        compute_emi(*args)


def test_score_range():
    assert compute_score({}) == 0
    full = {"budget_max": 1, "location_pref": "x", "bhk": 2, "purpose": "buy",
            "financing": "loan", "timeline": "this month"}
    assert compute_score(full) == 100
