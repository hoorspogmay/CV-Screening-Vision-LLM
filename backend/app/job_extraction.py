"""LLM-based recruitment document job extraction."""
from __future__ import annotations

import logging
import re

from app.ai_provider import get_ai_provider
from app.job_extraction_types import JobExtraction

logger = logging.getLogger(__name__)

_EXPLICIT_JOB_HEADING_PATTERNS = [
    r"\bposition\b",
    r"\bvacancy\b",
    r"\bjob\s+title\b",
    r"\brole\b",
    r"\bopening\b",
]


def _has_explicit_job_heading(text: str) -> bool:
    return any(
        re.search(p, text, flags=re.IGNORECASE)
        for p in _EXPLICIT_JOB_HEADING_PATTERNS
    )


def _validate_extracted_jobs(jobs: list[JobExtraction], document_text: str) -> list[JobExtraction]:
    if jobs is None:
        raise ValueError("Job extraction response was empty.")
    if not isinstance(jobs, list):
        raise ValueError("Job extraction response must be a list of jobs.")
    if not jobs and _has_explicit_job_heading(document_text):
        raise ValueError(
            "Document contains explicit job headings but the extraction returned no jobs."
        )

    titles: list[str] = []
    for job in jobs:
        if not job.job_title.strip():
            raise ValueError("Job extraction returned a job with an empty title.")
        if not job.job_text.strip():
            raise ValueError(f"Job '{job.job_title}' has empty job_text.")
        titles.append(job.job_title.strip().lower())

    if len(titles) != len(set(titles)):
        raise ValueError("Job extraction returned duplicate job titles.")

    return jobs


async def extract_jobs_from_recruitment_document(document_text: str) -> list[JobExtraction]:
    """Extract job openings from the given recruitment document text.

    Raises RuntimeError if the active provider does not support extraction.
    """
    provider = get_ai_provider()

    try:
        jobs = await provider.extract_jobs(document_text)
    except NotImplementedError:
        raise RuntimeError(
            f"The active AI provider ({type(provider).__name__}) does not support "
            "job extraction. Override extract_jobs() in that provider class."
        )

    jobs = _validate_extracted_jobs(jobs, document_text)

    logger.info(
        "Validated job extraction | jobs=%d | titles=%s | word_counts=%s",
        len(jobs),
        [j.job_title for j in jobs],
        [len(j.job_text.split()) for j in jobs],
    )
    return jobs