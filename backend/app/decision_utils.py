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

    if match_score is None:
        if reasoning_text:
            score = score_from_reasoning(reasoning_text)
        else:
            return fallback_decision
    else:
        try:
            score = float(match_score)
        except (TypeError, ValueError):
            score = score_from_reasoning(reasoning_text)

    score = max(0.0, min(100.0, score))
    accept_threshold = 80
    doubtful_threshold = 50

    if score >= accept_threshold:
        return Decision.ACCEPT
    # Allow an override for minor single-skill gaps when the reasoning is strongly positive.
    if _should_accept_for_minor_skill_gap(reasoning_text):
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
        "not enough", "no relevant experience", "no relevant skills", "fails", "fails requirement",
        "fails mandatory", "fails the role", "does not satisfy", "not mentioned",
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


def parse_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)", value)
            if match:
                return float(match.group(1))
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        digits = re.search(r"(\d+)", value)
        if digits:
            try:
                return int(digits.group(1))
            except ValueError:
                return None
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def infer_experience_years(text: str | None) -> int | None:
    summary = (text or "").lower()
    if not summary:
        return None

    patterns = [
        r"\b(\d+)\s*\+\s*years?\b",
        r"\b(\d+)\s*(?:-|–|—|to)\s*(\d+)\s*years?\b",
        r"\b(?:over|more than|at least|minimum|min(?:imum)?)\s+(\d+)\s*years?\b",
        r"\b(\d+)\s*years?\b",
    ]

    values: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, summary):
            if match.lastindex is None:
                continue
            if match.lastindex == 1:
                values.append(int(match.group(1)))
            elif match.lastindex >= 2:
                values.append(int(match.group(1)))

    values = [value for value in values if value >= 0]
    if not values:
        return None

    return min(values)


def _detect_degree_level(text: str | None) -> str | None:
    t = (text or "").lower()
    if not t:
        return None
    if any(k in t for k in ("phd", "doctorate", "doctor of")):
        return "PhD"
    if any(k in t for k in ("master", "msc", "m.sc", "m.a", "m.a.", "m.s")):
        return "Master"
    if any(k in t for k in ("bachelor", "b.sc", "b.a", "ba", "bs", "b.s", "bachelors", "bachelor's")):
        return "Bachelor"
    return None


def reconcile_extracted_fields(
    summary: str | None,
    experience_years: int | None,
    skills_match: bool | None,
    education_level: str | None,
) -> tuple[int | None, bool | None, str | None]:
    """Normalize provider-extracted fields so they don't contradict the natural-language summary.

    Rules (minimal, evidence-based):
    - If `experience_years` is 0 but the summary contains explicit year spans or numbers, use inferred years.
    - If `experience_years` is 0 and the summary does not state "no experience", prefer `None` (unknown) rather than 0.
    - If `skills_match` is False but the summary contains positive skill indicators and no strong negatives, set to True.
    - If `education_level` is empty/unknown but a degree term appears in the summary, set the detected degree.
    """
    s = (summary or "").strip()
    s_lower = s.lower()

    # Experience reconciliation
    if experience_years == 0:
        if "no relevant experience" in s_lower or "no experience" in s_lower or "without experience" in s_lower:
            # explicit zero — keep 0
            pass
        else:
            inferred = infer_experience_years(s)
            if inferred is not None:
                experience_years = inferred
            else:
                experience_years = None

    # Skills reconciliation
    if skills_match is False:
        # Reuse markers from score_from_reasoning heuristics
        positive_markers = [
            "strong fit", "good fit", "well matched", "meets", "matches", "suitable", "qualified",
            "relevant experience", "relevant skills", "strongly aligns", "good alignment", "clear fit",
            "meets the role requirements", "solid background", "appropriate experience", "align",
        ]
        negative_markers = [
            "weak fit", "poor fit", "does not meet", "doesn't meet", "not suitable", "not qualified",
            "lacks", "missing", "insufficient", "unrelated", "inadequate", "fails",
        ]
        has_positive = any(tok in s_lower for tok in positive_markers)
        has_negative = any(tok in s_lower for tok in negative_markers)
        if has_positive and not has_negative:
            skills_match = True

    # Education reconciliation
    ed = (education_level or "").strip()
    if not ed or ed.lower() in {"none", "unknown", "n/a", "null"}:
        detected = _detect_degree_level(s)
        if detected:
            education_level = detected

    return experience_years, skills_match, education_level
