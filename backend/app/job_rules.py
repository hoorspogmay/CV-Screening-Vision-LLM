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
        requirement = requirements.required_education.lower().strip()
        if "bachelor" in requirement:
            if education_level in {"bachelor", "bachelors", "equivalent bachelor", "equivalent bachelor's", "equivalent degree", "bachelor's"}:
                pass
            elif education_level in {"master", "master's", "equivalent master", "equivalent master's", "equivalent master's degree"}:
                pass
            elif education_level in {"phd", "doctorate"}:
                if requirements.allow_overqualified:
                    pass
                else:
                    return Decision.REJECT
            else:
                return Decision.REJECT
        elif "master" in requirement:
            if education_level in {"master", "master's", "equivalent master", "equivalent master's"}:
                pass
            elif education_level in {"bachelor", "bachelor's"}:
                return Decision.REJECT
            elif education_level in {"phd", "doctorate"}:
                if requirements.allow_overqualified:
                    pass
                else:
                    return Decision.REJECT
            else:
                return Decision.REJECT
        elif "phd" in requirement or "doctorate" in requirement:
            if education_level in {"phd", "doctorate"}:
                pass
            else:
                return Decision.REJECT
        elif requirement not in {"", "none"}:
            if education_level == "none" and not requirements.allow_overqualified:
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
    if requirements.required_skills:
        if skills_match_signal is False:
            return Decision.REJECT
        if skills_match_signal is True:
            pass
        else:
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
