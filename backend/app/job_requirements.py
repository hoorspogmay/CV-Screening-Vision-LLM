"""Pydantic models for recruiter-defined hiring requirements."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class JobRequirements(BaseModel):
    """Requirements that define how a resume should be screened for a role."""

    job_role: str = "General Professional Role"
    required_education: str = ""
    min_experience: Optional[int] = None
    max_experience: Optional[int] = None
    required_skills: list[str] = Field(default_factory=list)
    allow_overqualified: bool = False
    allow_internships: bool = False

    @field_validator("min_experience", "max_experience", mode="before")
    @classmethod
    def normalize_experience(cls, value: object) -> Optional[int]:
        if value in (None, "", "None", "null"):
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return int(stripped)
        return int(value)
