"""Deterministic hiring-policy rules for generic recruitment screening."""
from __future__ import annotations

import re
from typing import Any

from app.schemas import Decision
from app.job_requirements import JobRequirements


def apply_business_rules(requirements: JobRequirements, ai_payload: dict[str, Any]) -> tuple[Decision, str]:
    """Apply deterministic rules and return final decision plus explanation."""
    decision = _determine_decision(requirements, ai_payload)
    reason = _build_reason(requirements, ai_payload, decision)
    return decision, reason


def _normalize_degree_level(level: str) -> str:
    text = (level or "").lower().strip()
    if not text:
        return "none"
    if any(k in text for k in ("phd", "doctorate")):
        return "phd"
    if any(k in text for k in ("master", "msc", "m.sc", "mba", "m.a", "m.s")):
        return "master"
    if any(k in text for k in ("bachelor", "bsc", "b.sc", "ba", "bs", "b.s", "bachelors", "bachelor's", "undergraduate", "college")):
        return "bachelor"
    if any(k in text for k in ("associate", "aa", "as", "associate's")):
        return "associate"
    if any(k in text for k in ("diploma", "certificate", "cert", "high school", "secondary")):
        return "other"
    if "degree" in text:
        return "bachelor"
    return "none"


def _education_matches_requirement(
    requirement: str,
    education_level: str,
    education_relevant: bool | None,
    experience_years: int | None,
    experience_relevant: bool | None,
    min_experience: int | None,
) -> bool:
    req = (requirement or "").lower().strip()
    cand = _normalize_degree_level(education_level)
    related_requirement = any(keyword in req for keyword in ("related", "equivalent", "or equivalent", "or related"))

    if not req or req in {"none", "any"}:
        return True

    if "bachelor" in req:
        if cand in {"bachelor", "master", "phd"}:
            return True
        if related_requirement and cand != "none":
            return True
        if education_relevant is True and experience_relevant is True and (experience_years or 0) >= 5:
            return True
        return False

    if "master" in req:
        if cand in {"master", "phd"}:
            return True
        if related_requirement and cand == "bachelor" and education_relevant is True and experience_relevant is True and (experience_years or 0) >= max(min_experience or 0, 7):
            return True
        return False

    if "phd" in req or "doctorate" in req:
        return cand in {"phd", "doctorate"}

    if related_requirement and cand != "none":
        return True
    if education_relevant is True:
        return True
    return cand != "none"


def _determine_decision(requirements: JobRequirements, ai_payload: dict[str, Any]) -> Decision:
    education_level = str(ai_payload.get("education_level") or "").strip().lower()
    education_relevant = ai_payload.get("education_relevant")
    experience_years = ai_payload.get("experience_years")
    experience_relevant = ai_payload.get("experience_relevant")
    skills_match = bool(ai_payload.get("skills_match", True))

    # Only apply hard rule rejects when a recruiter has supplied the relevant requirement.
    if education_relevant is False and requirements.required_education:
        return Decision.REJECT
    if experience_relevant is False and (requirements.min_experience is not None or requirements.max_experience is not None):
        return Decision.REJECT

    # Respect an explicit signal from the AI about skills matching when present.
    skills_match_signal = ai_payload.get("skills_match", None)
    if skills_match_signal is False and requirements.required_skills:
        summary = str(ai_payload.get("skills_summary") or "").lower()
        reason = str(ai_payload.get("reason") or "").lower()
        if _summary_indicates_hard_skill_mismatch(summary) or _summary_indicates_hard_skill_mismatch(reason):
            return Decision.REJECT
        # Do not hard reject solely because skills_match is false.
        # The model may have flagged a gap in a preferred or minor skill.
        return Decision.DOUBTFUL

    if requirements.required_education:
        if not _education_matches_requirement(
            requirements.required_education,
            education_level,
            education_relevant,
            experience_years,
            experience_relevant,
            requirements.min_experience,
        ):
            return Decision.REJECT

    if requirements.min_experience is not None or requirements.max_experience is not None:
        if experience_relevant is True:
            try:
                years = int(experience_years or 0)
            except (TypeError, ValueError):
                years = 0

            if requirements.min_experience is not None and years < requirements.min_experience:
                return Decision.REJECT
            if requirements.max_experience is not None and years > requirements.max_experience:
                return Decision.REJECT

    # If the AI did not explicitly state skills_match, use the model's own narrative
    # rather than applying a hard deterministic reject for any missing required skill.
    if requirements.required_skills and skills_match_signal is None:
        skills_summary = str(ai_payload.get("skills_summary") or "")
        if not _has_required_skills(skills_summary, requirements.required_skills):
            if _summary_indicates_hard_skill_mismatch(skills_summary):
                return Decision.REJECT

    return Decision.ACCEPT


def _has_required_skills(skills_summary: str, required_skills: list[str]) -> bool:
    summary = (skills_summary or "").lower()
    for skill in required_skills:
        token = skill.lower().strip()
        if not token:
            continue
        # Match whole tokens to avoid accidental substring matches (e.g. "go" in "ngo").
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, summary):
            continue
        return False
    return True


def _summary_indicates_hard_skill_mismatch(skills_summary: str) -> bool:
    text = (skills_summary or "").lower()
    if not text:
        return False

    hard_negative_phrases = [
        "does not have",
        "doesn't have",
        "lacks required",
        "lacks the required",
        "no relevant",
        "not proficient",
        "not experienced",
        "fails requirement",
        "fails mandatory",
        "fails the role",
        "does not meet",
        "doesn't meet",
        "not qualified",
        "not suitable",
        "poor fit",
    ]
    if any(phrase in text for phrase in hard_negative_phrases):
        return True

    mild_context = [
        "minor",
        "small",
        "one",
        "single",
        "preferred",
        "optional",
        "still strong",
        "overall strong",
        "good fit",
        "strong fit",
        "broadly",
        "still a good",
        "acceptable",
    ]
    negative_markers = [
        "missing",
        "lacks",
        "without",
        "insufficient",
        "weak on",
        "poor on",
        "not proficient",
        "not experienced",
    ]

    if any(marker in text for marker in negative_markers):
        if any(context in text for context in mild_context):
            return False
        return True

    return False


def _build_reason(requirements: JobRequirements, ai_payload: dict[str, Any], decision: Decision) -> str:
    base = ai_payload.get("reason") or ""
    if decision == Decision.ACCEPT:
        return f"{base} Matches role requirements for {requirements.job_role}.".strip()
    return f"{base} Did not satisfy the configured hiring policy for {requirements.job_role}.".strip()
