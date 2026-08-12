from app.decision_utils import classify_by_match_score
from app.schemas import Decision


def test_score_60_results_in_doubtful() -> None:
    decision = classify_by_match_score(60, Decision.REJECT, None, reasoning=None)
    assert decision == Decision.DOUBTFUL


def test_fractional_score_0_6_results_in_doubtful() -> None:
    decision = classify_by_match_score(0.6, Decision.REJECT, None, reasoning=None)
    assert decision == Decision.DOUBTFUL
