"""Deterministic hiring-policy rules for generic recruitment screening."""
from __future__ import annotations

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
    education_relevant = bool(ai_payload.get("education_relevant", True))
    experience_years = ai_payload.get("experience_years")
    experience_relevant = bool(ai_payload.get("experience_relevant", True))
    skills_match = bool(ai_payload.get("skills_match", True))

    if not education_relevant or not experience_relevant:
        return Decision.REJECT

    if not skills_match:
        summary = str(ai_payload.get("skills_summary") or "").lower()
        reason = str(ai_payload.get("reason") or "").lower()
        if "minor" in summary or "minor" in reason or "one" in summary or "one" in reason:
            return Decision.ACCEPT
        return Decision.REJECT

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
        try:
            years = int(experience_years or 0)
        except (TypeError, ValueError):
            years = 0

        if requirements.min_experience is not None and years < requirements.min_experience:
            return Decision.REJECT
        if requirements.max_experience is not None and years > requirements.max_experience:
            return Decision.REJECT

    if requirements.required_skills and not _has_required_skills(ai_payload.get("skills_summary", ""), requirements.required_skills):
        return Decision.REJECT

    return Decision.ACCEPT


def _has_required_skills(skills_summary: str, required_skills: list[str]) -> bool:
    summary = (skills_summary or "").lower()
    for skill in required_skills:
        token = skill.lower().strip()
        if not token:
            continue
        if token in summary:
            continue
        return False
    return True


def _build_reason(requirements: JobRequirements, ai_payload: dict[str, Any], decision: Decision) -> str:
    base = ai_payload.get("reason") or ""
    if decision == Decision.ACCEPT:
        return f"{base} Matches role requirements for {requirements.job_role}.".strip()
    return f"{base} Did not satisfy the configured hiring policy for {requirements.job_role}.".strip()
