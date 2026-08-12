"""
Abstract interface every AI provider must implement.

Adding a new provider means:
  1. Creating app/providers/<name>_provider.py that subclasses AIProvider
  2. Registering it in ai_provider.py
  3. Setting AI_PROVIDER=<name> in .env

Nothing else in the app changes.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from app.job_extraction_types import JobExtraction
from app.job_requirements import JobRequirements
from app.schemas import Decision, ResumeResult
from app.decision_utils import (
    classify_by_match_score,
    infer_experience_years,
    parse_optional_int,
)

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Contract for a resume-screening AI backend."""

    @abstractmethod
    async def evaluate_resume(
        self,
        resume_text: str,
        file_name: str,
        file_id: str,
        requirements: JobRequirements | None = None,
        recruitment_document_text: str | None = None,
    ) -> ResumeResult:
        """
        Send resume text to the LLM and return a structured ResumeResult.

        Implementations are responsible for:
          - building the prompt
          - calling the provider's API
          - parsing the response into the ACCEPT/DOUBTFUL/REJECT shape
          - retrying on transient failures
        Any unrecoverable failure should raise an exception.
        """
        raise NotImplementedError

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 200,
        temperature: float = 0.0,
    ) -> str:
        """Send a lightweight completion request and return the raw response text."""
        raise NotImplementedError

    async def extract_jobs(self, document_text: str) -> list[JobExtraction]:
        """
        Extract job openings from a recruitment document.

        Providers that support job extraction must override this method.
        The default implementation raises NotImplementedError so that
        job_extraction.py can detect unsupported providers cleanly.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support job extraction. "
            "Override extract_jobs() to add support."
        )

    @staticmethod
    def parse_resume_json(
        content: str,
        file_name: str,
        file_id: str,
        requirements: JobRequirements | None = None,
    ) -> ResumeResult:
        """
        Shared JSON → ResumeResult parser used by all providers.

        Centralising the parsing here means fixes and improvements apply to
        every provider at once, and provider classes stay focused on HTTP.
        """
        cleaned = (
            content.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        data = json.loads(cleaned)

        candidate_name = str(data.get("candidate_name") or "").strip()
        if not candidate_name or candidate_name.lower() in {"unknown", "n/a", "null"}:
            candidate_name = "Unknown"

        try:
            match_score = float(data.get("match_score", 0))
        except (TypeError, ValueError):
            match_score = 0.0

        decision_value = str(data.get("decision") or "").strip().upper()
        if decision_value not in {Decision.ACCEPT.value, Decision.REJECT.value, Decision.DOUBTFUL.value}:
            summary_text = str(
                data.get("summary") or data.get("reason") or ""
            )
            decision_value = classify_by_match_score(
                match_score,
                Decision.REJECT,
                requirements,
                reasoning=summary_text,
            ).value

        experience_years = parse_optional_int(data.get("experience_years"))
        summary_text = str(
            data.get("experience_summary")
            or data.get("experience")
            or data.get("summary")
            or data.get("reason")
            or ""
        )
        inferred_years = infer_experience_years(summary_text)
        if experience_years is None:
            experience_years = inferred_years
        elif experience_years == 0 and inferred_years is not None:
            text_lower = summary_text.lower()
            if "no relevant experience" not in text_lower and "no experience" not in text_lower:
                experience_years = inferred_years

        return ResumeResult(
            file_id=file_id,
            file_name=file_name,
            candidate_name=candidate_name,
            decision=Decision(decision_value),
            summary=data.get("summary", ""),
            match_score=match_score,
            education_level=str(data.get("education_level") or "None").strip(),
            experience_years=experience_years,
            skills_match=bool(data.get("skills_match", True)),
        )