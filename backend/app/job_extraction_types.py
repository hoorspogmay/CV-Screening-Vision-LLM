from __future__ import annotations

import json
from pydantic import BaseModel, Field, ValidationError


def _clean_json_text(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[: -len("```")].strip()
    return cleaned


class JobExtraction(BaseModel):
    job_title: str = Field(..., min_length=1)
    job_text: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=100)
    evidence: str = Field(..., min_length=1)


class JobExtractionResponse(BaseModel):
    jobs: list[JobExtraction] = Field(default_factory=list)


def parse_job_extraction_response(content: str) -> list[JobExtraction]:
    cleaned = _clean_json_text(content)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Job extraction response is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Job extraction response must be a JSON object with a jobs list.")

    try:
        response = JobExtractionResponse(**payload)
    except ValidationError as exc:
        raise ValueError(f"Job extraction JSON did not match the expected schema: {exc}") from exc

    return response.jobs
