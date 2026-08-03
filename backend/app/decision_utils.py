from __future__ import annotations

import re

from app.job_requirements import JobRequirements
from app.schemas import Decision


def classify_by_match_score(
    match_score: float | None,
    fallback_decision: Decision,
    requirements: JobRequirements | None = None,
    reasoning: str | None = None,
) -> Decision:
    reasoning_text = reasoning or ""

    if _should_accept_for_minor_skill_gap(reasoning_text):
        return Decision.ACCEPT

    if match_score is None:
        return fallback_decision

    try:
        score = float(match_score)
    except (TypeError, ValueError):
        score = score_from_reasoning(reasoning_text)

    accept_threshold = requirements.accept_threshold if requirements is not None else 80
    doubtful_threshold = requirements.doubtful_threshold if requirements is not None else 50

    if score >= accept_threshold:
        return Decision.ACCEPT
    if score >= doubtful_threshold:
        return Decision.DOUBTFUL
    return Decision.REJECT


def _should_accept_for_minor_skill_gap(reasoning: str) -> bool:
    text = (reasoning or "").lower()
    if not text:
        return False

    minor_gap_patterns = [
        "minor gap",
        "minor missing",
        "small gap",
        "slight gap",
        "one skill",
        "single skill",
        "one missing",
        "single missing",
    ]
    positive_markers = [
        "strong fit",
        "good fit",
        "well matched",
        "well qualified",
        "overall strong",
        "overall good",
        "meets the role requirements",
        "meets the requirements",
        "should be accepted",
        "broadly satisfies",
        "clearly qualified",
        "suitable",
    ]
    negative_markers = [
        "does not meet",
        "doesn't meet",
        "not suitable",
        "not qualified",
        "poor fit",
        "weak fit",
        "lacks",
        "missing experience",
        "missing skills",
        "no relevant experience",
        "no relevant skills",
    ]

    has_minor_gap = any(pattern in text for pattern in minor_gap_patterns)
    has_positive_fit = any(marker in text for marker in positive_markers)
    has_strong_negative = any(marker in text for marker in negative_markers)

    return has_minor_gap and has_positive_fit and not has_strong_negative


def score_from_reasoning(reasoning: str) -> float:
    text = (reasoning or "").lower()
    if not text:
        return 0.0

    positive_markers = [
        "strong fit", "good fit", "well matched", "meets", "matches", "suitable", "qualified",
        "relevant experience", "relevant skills", "strongly aligns", "good alignment", "clear fit",
        "meets the role requirements", "solid background", "appropriate experience"
    ]
    negative_markers = [
        "weak fit", "poor fit", "does not meet", "doesn't meet", "not suitable", "not qualified",
        "lacks", "missing", "insufficient", "unrelated", "inadequate", "does not match",
        "not enough", "no relevant experience", "no relevant skills"
    ]

    positive_hits = sum(1 for marker in positive_markers if marker in text)
    negative_hits = sum(1 for marker in negative_markers if marker in text)

    if positive_hits and negative_hits:
        return 50.0 + (positive_hits - negative_hits) * 5.0
    if positive_hits:
        return min(90.0, 70.0 + positive_hits * 5.0)
    if negative_hits:
        return max(10.0, 40.0 - negative_hits * 6.0)

    return 50.0
