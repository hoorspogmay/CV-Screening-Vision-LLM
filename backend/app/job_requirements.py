"""Pydantic models for recruiter-defined hiring requirements."""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.job_extraction_types import JobExtraction
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


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


class JobOpeningProfile(BaseModel):
    """A distinct job opening extracted from the recruitment document."""

    title: str = ""
    requirements: JobRequirements = Field(default_factory=JobRequirements)
    description: str = ""


def _find_value(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match and match.group(1):
            return match.group(1).strip()
    return ""


def _find_int(text: str, patterns: list[str]) -> Optional[int]:
    value = _find_value(text, patterns)
    if not value:
        return None
    digits = re.search(r"(\d+)", value)
    return int(digits.group(1)) if digits else None


def _find_bool(text: str, patterns: list[str]) -> bool:
    value = _find_value(text, patterns)
    if not value:
        return False
    return value.lower() in {"yes", "true", "1", "allow", "allowed"}


def _find_skills(text: str) -> list[str]:
    value = _find_value(text, [
        r"required\s+skills\s*[:\-]\s*(.+)",
        r"skills\s*[:\-]\s*(.+)",
    ])
    if not value:
        return []
    parts = re.split(r"[,;\n]+", value)
    return [part.strip() for part in parts if part and part.strip()]


def _parse_requirements_from_text(spec_text: str, fallback_role: str = "") -> JobRequirements:
    text = (spec_text or "").strip()
    if not text:
        return JobRequirements()

    role = _find_value(text, [
        r"job\s*role\s*[:\-]\s*(.+)",
        r"job\s*title\s*[:\-]\s*(.+)",
        r"role\s*[:\-]\s*(.+)",
    ]) or fallback_role
    education = _find_value(text, [
        r"required\s*education\s*[:\-]\s*(.+)",
        r"education\s*[:\-]\s*(.+)",
    ])
    min_experience = _find_int(text, [
        r"minimum\s*experience\s*[:\-]\s*(.+)",
        r"min\s*experience\s*[:\-]\s*(.+)",
    ])
    max_experience = _find_int(text, [
        r"maximum\s*experience\s*[:\-]\s*(.+)",
        r"max\s*experience\s*[:\-]\s*(.+)",
    ])
    allow_overqualified = _find_bool(text, [r"allow\s*overqualified\s*[:\-]\s*(.+)"])
    allow_internships = _find_bool(text, [r"allow\s*internships\s*[:\-]\s*(.+)"])

    return JobRequirements(
        job_role=role or "General Professional Role",
        required_education=education,
        min_experience=min_experience,
        max_experience=max_experience,
        required_skills=_find_skills(text),
        allow_overqualified=allow_overqualified,
        allow_internships=allow_internships,
    )


def build_job_requirements_from_text(spec_text: str) -> JobRequirements:
    """Parse one job specification document into recruiter requirements."""
    profiles = build_job_profiles_from_text(spec_text)
    if profiles:
        return profiles[0].requirements
    return _parse_requirements_from_text(spec_text)


def _looks_like_job_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return bool(re.match(
        r"^\s*(?:job\s+opening|opening|vacancy|position|job\s+role|job\s+title|role)\s*(?:#?\d+)?\s*(?:[:\-]|$)",
        stripped,
        flags=re.IGNORECASE,
    ))


def _is_generic_header(title: str) -> bool:
    generic_markers = {
        "department",
        "division",
        "team",
        "group",
        "business",
        "organization",
        "office",
        "location",
        "company",
        "program",
    }
    normalized = title.strip().lower()
    return any(marker in normalized for marker in generic_markers)


def _split_job_opening_sections(spec_text: str) -> list[tuple[str, str]]:
    lines = [line.rstrip() for line in (spec_text or "").splitlines()]
    sections: list[tuple[str, str]] = []
    section_bounds: list[tuple[int, int, str]] = []
    current_title = ""
    current_lines: list[str] = []
    current_start = 0
    found_job_header = False
    preamble_lines: list[str] = []
    ambiguous_headers: list[str] = []

    def flush(end_line: int) -> None:
        if current_lines:
            section_text = "\n".join(current_lines).strip()
            if section_text:
                sections.append((current_title.strip(), section_text))
                section_bounds.append((current_start, end_line, current_title.strip() or "<generic>"))

    for line_index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if _looks_like_job_header(line):
            extracted_title = re.sub(
                r"^\s*(?:job\s+opening|opening|vacancy|position|job\s+role|job\s+title|role)\s*(?:#?\d+)?\s*(?:[:\-])\s*",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()
            if _is_generic_header(extracted_title) or not extracted_title:
                ambiguous_headers.append(line)
                if found_job_header:
                    current_lines.append(raw_line)
                else:
                    preamble_lines.append(raw_line)
                continue

            if found_job_header:
                flush(line_index - 1)
            current_title = extracted_title
            current_lines = preamble_lines + [raw_line] if preamble_lines else [raw_line]
            preamble_lines = []
            current_start = line_index
            found_job_header = True
        elif found_job_header:
            current_lines.append(raw_line)
        else:
            preamble_lines.append(raw_line)

    flush(len(lines) - 1)
    if not sections:
        if ambiguous_headers:
            logger.debug(
                "Job extraction found no explicit job headers but saw generic sections: %s",
                ambiguous_headers,
            )
        return [("", (spec_text or "").strip())]

    logger.debug(
        "Detected %d job sections: titles=%s; boundaries=%s; ambiguous_headers=%s",
        len(sections),
        [title for title, _ in sections],
        [f"{start}-{end}:{title}" for start, end, title in section_bounds],
        ambiguous_headers,
    )
    return sections


def build_job_profiles_from_text(spec_text: str) -> list[JobOpeningProfile]:
    """Parse a recruitment document into distinct internal job opening profiles."""
    text = (spec_text or "").strip()
    if not text:
        return []

    sections = _split_job_opening_sections(text)
    profiles: list[JobOpeningProfile] = []
    seen_titles: set[str] = set()

    for title, section_text in sections:
        requirements = _parse_requirements_from_text(section_text, title)
        final_title = title or requirements.job_role or "General Professional Role"
        normalized_title = final_title.strip().lower()
        if not normalized_title:
            continue
        if normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)
        profiles.append(
            JobOpeningProfile(
                title=final_title.strip(),
                requirements=requirements,
                description=section_text,
            )
        )

    if not profiles:
        requirements = _parse_requirements_from_text(text)
        profiles.append(
            JobOpeningProfile(
                title=requirements.job_role or "General Professional Role",
                requirements=requirements,
                description=text,
            )
        )

    return profiles


def build_job_profiles_from_extraction(jobs: list[JobExtraction]) -> list[JobOpeningProfile]:
    profiles: list[JobOpeningProfile] = []
    seen_titles: set[str] = set()

    for job in jobs:
        final_title = job.job_title.strip() or "General Professional Role"
        normalized_title = final_title.lower()
        if not final_title or normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)

        profile = JobOpeningProfile(
            title=final_title,
            requirements=_parse_requirements_from_text(job.job_text, final_title),
            description=job.job_text,
        )
        profiles.append(profile)

    return profiles
