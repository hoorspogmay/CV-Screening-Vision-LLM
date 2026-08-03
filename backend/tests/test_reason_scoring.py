from app.decision_utils import classify_by_match_score, score_from_reasoning
from app.schemas import Decision


def test_score_from_reasoning_maps_positive_reasoning_to_higher_value() -> None:
    score = score_from_reasoning("Strong fit with relevant experience and matching skills. Candidate clearly meets the role requirements.")
    assert score >= 75


def test_score_from_reasoning_maps_negative_reasoning_to_lower_value() -> None:
    score = score_from_reasoning("Weak fit due to missing experience and skills. Candidate does not meet the role requirements.")
    assert score <= 45


def test_minor_single_skill_gap_is_treated_as_accept_when_overall_fit_is_good() -> None:
    decision = classify_by_match_score(
        65,
        Decision.REJECT,
        None,
        reasoning="Overall strong fit with relevant experience and matching skills. Minor gap in one skill, but the candidate is otherwise well qualified and should be accepted.",
    )
    assert decision == Decision.ACCEPT

    score = score_from_reasoning(
        "Overall strong fit with relevant experience and matching skills. Minor gap in one skill, but the candidate is otherwise well qualified and should be accepted."
    )
    assert score >= 80
