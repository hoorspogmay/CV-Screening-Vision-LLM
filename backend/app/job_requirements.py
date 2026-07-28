"""Pydantic models for recruiter-defined hiring requirements."""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class JobRequirements(BaseModel):
    """Requirements that define how a resume should be screened for a role."""

    job_role: str = "General Professional Role"
    required_education: str = ""
    min_experience: Optional[int] = None
    max_experience: Optional[int] = None
    accept_threshold: int = 80
    doubtful_threshold: int = 50
    required_skills: list[str] = Field(default_factory=list)
    allow_overqualified: bool = False
    allow_internships: bool = False

    @field_validator("min_experience", "max_experience", "accept_threshold", "doubtful_threshold", mode="before")
    @classmethod
    def normalize_int(cls, value: object) -> Optional[int]:
        if value in (None, "", "None", "null"):
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return int(stripped)
        return int(value)


def build_job_requirements_from_text(spec_text: str) -> JobRequirements:
    """Parse a job specification document into recruiter requirements."""
    text = (spec_text or "").strip()
    if not text:
        return JobRequirements()

    def _find_value(patterns: list[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
            if match and match.group(1):
                return match.group(1).strip()
        return ""

    def _find_int(patterns: list[str]) -> Optional[int]:
        value = _find_value(patterns)
        if not value:
            return None
        digits = re.search(r"(\d+)", value)
        return int(digits.group(1)) if digits else None

    def _find_bool(patterns: list[str]) -> bool:
        value = _find_value(patterns)
        if not value:
            return False
        return value.lower() in {"yes", "true", "1", "allow", "allowed"}

    def _find_skills() -> list[str]:
        value = _find_value([
            r"required\s+skills\s*[:\-]\s*(.+)",
            r"skills\s*[:\-]\s*(.+)",
        ])
        if not value:
            return []
        parts = re.split(r"[,;\n]+", value)
        return [part.strip() for part in parts if part and part.strip()]

    role = _find_value([
        r"job\s*role\s*[:\-]\s*(.+)",
        r"job\s*title\s*[:\-]\s*(.+)",
        r"role\s*[:\-]\s*(.+)",
    ])
    education = _find_value([
        r"required\s*education\s*[:\-]\s*(.+)",
        r"education\s*[:\-]\s*(.+)",
    ])
    min_experience = _find_int([
        r"minimum\s*experience\s*[:\-]\s*(.+)",
        r"min\s*experience\s*[:\-]\s*(.+)",
    ])
    max_experience = _find_int([
        r"maximum\s*experience\s*[:\-]\s*(.+)",
        r"max\s*experience\s*[:\-]\s*(.+)",
    ])
    allow_overqualified = _find_bool([r"allow\s*overqualified\s*[:\-]\s*(.+)"])
    allow_internships = _find_bool([r"allow\s*internships\s*[:\-]\s*(.+)"])

    return JobRequirements(
        job_role=role or "General Professional Role",
        required_education=education,
        min_experience=min_experience,
        max_experience=max_experience,
        required_skills=_find_skills(),
        allow_overqualified=allow_overqualified,
        allow_internships=allow_internships,
    )
