"""
Resume screening orchestration.

A "job" is one batch of uploaded resumes. Each job is processed
concurrently (bounded by MAX_CONCURRENT_EVALUATIONS) and every finished
resume is broadcast immediately to any WebSocket clients subscribed to
that job, so the UI can show results as they land rather than waiting for
the whole batch.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings
from app.schemas import (
    Decision,
    JobProgress,
    JobStatus,
    ResumeResult,
    WSEvent,
    WSEventType,
)
from app.ai_provider import get_ai_provider, get_fallback_provider
from app.job_requirements import JobRequirements
from app.job_rules import apply_business_rules
from app.file_utils import extract_text
from app.decision_utils import classify_by_match_score


class RecruitmentDocumentContext:
    """Small container for the full recruitment document text associated with a job."""

    def __init__(self, document_text: str = "") -> None:
        self.document_text = document_text or ""

logger = logging.getLogger(__name__)


@dataclass
class JobState:
    job_id: str
    total: int
    status: JobStatus = JobStatus.PENDING
    results: list[ResumeResult] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    temp_dir: Path | None = None
    requirements: JobRequirements | None = None
    recruitment_document_context: RecruitmentDocumentContext | None = None

    @property
    def processed(self) -> int:
        return len(self.results)

    @property
    def accepted(self) -> int:
        return sum(1 for r in self.results if r.decision == Decision.ACCEPT and not r.error)

    @property
    def doubtful(self) -> int:
        return sum(1 for r in self.results if r.decision == Decision.DOUBTFUL and not r.error)

    @property
    def rejected(self) -> int:
        return sum(1 for r in self.results if r.decision == Decision.REJECT and not r.error)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.error)

    def progress(self) -> JobProgress:
        return JobProgress(
            job_id=self.job_id,
            status=self.status,
            total=self.total,
            processed=self.processed,
            accepted=self.accepted,
            doubtful=self.doubtful,
            rejected=self.rejected,
            failed=self.failed,
        )


class JobManager:
    """In-memory registry of screening jobs. One process, no external store needed."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}

    def create_job(
        self,
        total_files: int,
        requirements: JobRequirements | None = None,
        recruitment_document_context: RecruitmentDocumentContext | None = None,
    ) -> JobState:
        job_id = str(uuid.uuid4())
        job = JobState(
            job_id=job_id,
            total=total_files,
            requirements=requirements,
            recruitment_document_context=recruitment_document_context,
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    async def broadcast(self, job: JobState, event: WSEvent) -> None:
        """Push an event to every currently-subscribed WebSocket for this job."""
        for queue in list(job.subscribers):
            await queue.put(event)

    def subscribe(self, job: JobState) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        job.subscribers.append(queue)
        return queue

    def unsubscribe(self, job: JobState, queue: asyncio.Queue) -> None:
        if queue in job.subscribers:
            job.subscribers.remove(queue)

    def cleanup_job_files(self, job: JobState) -> None:
        if job.temp_dir and job.temp_dir.exists():
            shutil.rmtree(job.temp_dir, ignore_errors=True)


job_manager = JobManager()


def _error_result(file_id: str, file_name: str, error: str) -> ResumeResult:
    """Construct a failed ResumeResult using the current schema."""
    return ResumeResult(
        file_id=file_id,
        file_name=file_name,
        candidate_name="Unknown",
        decision=Decision.REJECT,
        summary="Processing failed.",
        error=error,
    )


async def process_single_resume(job: JobState, file_path: Path, file_name: str) -> ResumeResult:
    """Extract text, evaluate with the AI provider, and return a result (never raises)."""
    file_id = str(uuid.uuid4())
    primary_provider = get_ai_provider()
    try:
        text = await asyncio.to_thread(extract_text, file_path)
        result = await primary_provider.evaluate_resume(
            text,
            file_name,
            file_id,
            requirements=job.requirements,
            recruitment_document_text=(job.recruitment_document_context.document_text if job.recruitment_document_context else ""),
        )
        return _finalize_result(result, job.requirements)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Primary provider failed for %s: %s", file_name, exc)
        fallback = get_fallback_provider(primary_provider)
        if fallback is primary_provider:
            return _error_result(file_id, file_name, str(exc))

        try:
            text = await asyncio.to_thread(extract_text, file_path)
            result = await fallback.evaluate_resume(
                text,
                file_name,
                file_id,
                requirements=job.requirements,
                recruitment_document_text=(job.recruitment_document_context.document_text if job.recruitment_document_context else ""),
            )
            return _finalize_result(result, job.requirements)
        except Exception as fallback_exc:  # noqa: BLE001
            logger.warning("Fallback provider also failed for %s: %s", file_name, fallback_exc)
            return _error_result(file_id, file_name, str(fallback_exc))


def _finalize_result(result: ResumeResult, requirements: JobRequirements | None) -> ResumeResult:
    """Classify the result.

    Priority order:
    1. If business rules say hard REJECT (policy violation), always reject.
    2. Otherwise, classify by match_score: >=80 ACCEPT, >=50 DOUBTFUL, <50 REJECT.
    """
    # Step 1 — check for a hard policy REJECT from business rules
    if requirements is not None:
        ai_payload = {
            "education_level": str(result.education_level or "none").strip().lower(),
            "education_relevant": True,
            "experience_years": result.experience_years,
            "experience_relevant": True,
            "skills_match": bool(result.skills_match if result.skills_match is not None else True),
            "reason": result.summary,
            "skills_summary": result.summary,
        }
        rules_decision, _ = apply_business_rules(requirements, ai_payload)
        if rules_decision == Decision.REJECT:
            # Hard policy gate — candidate violates a recruiter-defined constraint
            if result.decision != Decision.REJECT:
                return result.model_copy(update={"decision": Decision.REJECT})
            return result

    # Step 2 — score drives the final decision
    final_decision = classify_by_match_score(
        result.match_score,
        result.decision,
        requirements,
        reasoning=result.summary,
    )
    if final_decision == result.decision:
        return result
    return result.model_copy(update={"decision": final_decision})


async def run_screening_job(job: JobState, file_paths: list[tuple[Path, str]]) -> None:
    """Background task: process every resume in the job concurrently and broadcast results."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.max_concurrent_evaluations)
    job.status = JobStatus.PROCESSING

    async def process_with_limit(path: Path, name: str) -> None:
        async with semaphore:
            result = await process_single_resume(job, path, name)
            job.results.append(result)
            await job_manager.broadcast(job, WSEvent(type=WSEventType.RESULT, result=result))
            await job_manager.broadcast(job, WSEvent(type=WSEventType.PROGRESS, progress=job.progress()))

    await asyncio.gather(*(process_with_limit(path, name) for path, name in file_paths))

    job.status = JobStatus.COMPLETED
    await job_manager.broadcast(job, WSEvent(type=WSEventType.DONE, progress=job.progress()))


def save_uploads_to_temp(files_data: list[tuple[str, bytes]]) -> tuple[Path, list[tuple[Path, str]]]:
    """Persist uploaded file bytes to a temp directory; returns (dir, [(path, original_name)])."""
    temp_dir = Path(tempfile.mkdtemp(prefix="ats_job_"))
    saved: list[tuple[Path, str]] = []
    for original_name, content in files_data:
        safe_name = f"{uuid.uuid4().hex}_{Path(original_name).name}"
        dest = temp_dir / safe_name
        dest.write_bytes(content)
        saved.append((dest, original_name))
    return temp_dir, saved