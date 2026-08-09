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
import re
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
from app.job_requirements import JobOpeningProfile, JobRequirements
from app.job_rules import apply_business_rules
from app.file_utils import extract_text
from app.decision_utils import classify_by_match_score, score_from_reasoning


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
    job_profiles: list[JobOpeningProfile] = field(default_factory=list)
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
        job_profiles: list[JobOpeningProfile] | None = None,
    ) -> JobState:
        job_id = str(uuid.uuid4())
        job = JobState(
            job_id=job_id,
            total=total_files,
            requirements=requirements,
            job_profiles=job_profiles or [],
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


def _normalize_routing_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    return " ".join(word for word in cleaned.split() if word not in {"the", "and", "for", "with", "from", "of", "to", "in", "on", "a", "an", "is", "are"})


def _expand_routing_terms(text: str) -> set[str]:
    normalized = _normalize_routing_text(text)
    if not normalized:
        return set()

    terms = set(normalized.split())
    expanded = set(terms)
    synonym_groups = {
        "engineer": {"engineer", "engineering", "developer", "software", "programmer", "swe", "backend", "frontend", "fullstack", "full-stack", "devops"},
        "analyst": {"analyst", "analytics", "analysis", "reporting", "dashboard", "bi", "insights", "metrics"},
        "manager": {"manager", "lead", "leadership", "coordinator", "director", "product", "owner"},
        "designer": {"designer", "ui", "ux", "visual", "experience", "interaction"},
        "data": {"data", "database", "warehouse", "etl", "science", "analytics", "sql", "postgres", "postgresql", "mysql", "db"},
        "sales": {"sales", "business", "account", "client", "revenue", "growth", "commercial"},
        "support": {"support", "service", "helpdesk", "customer", "operations"},
        "education": {"bsc", "bs", "ba", "bachelor", "bachelors", "bachelor's", "master", "masters", "msc", "ms", "phd", "doctorate", "graduate", "undergraduate"},
        "cloud": {"cloud", "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "devops"},
        "ai": {"ai", "ml", "machine", "learning", "deep", "llm", "nlp", "vision"},
        "web": {"web", "javascript", "js", "typescript", "ts", "react", "node", "vue", "angular", "frontend", "backend"},
        "mobile": {"mobile", "android", "ios", "swift", "kotlin"},
        "security": {"security", "cyber", "infosec", "soc", "pentest", "iam"},
        "healthcare": {"nurse", "nursing", "rn", "bsn", "lpn", "patient", "patient-care", "clinical", "icu", "acls", "bls", "hospital", "clinic", "vital", "patientcare"},
    }
    for term in list(terms):
        for root, group in synonym_groups.items():
            if term in group or root == term:
                expanded.update(group)
    return expanded


def _semantic_profile_score(resume_text: str, profile: JobOpeningProfile) -> float:
    profile_text = " ".join(
        part for part in [
            profile.title,
            profile.requirements.job_role,
            profile.requirements.required_education,
            " ".join(profile.requirements.required_skills),
        ] if part
    )
    resume_terms = _expand_routing_terms(resume_text)
    profile_terms = _expand_routing_terms(profile_text)
    if not resume_terms or not profile_terms:
        return 0.0

    resume_tokens = set(_normalize_routing_text(resume_text).split())

    # Title overlap: capture previous job titles and role labels as the strongest relevance signal.
    title_tokens = set(_normalize_routing_text(" ".join([profile.title or "", profile.requirements.job_role or ""])) .split())
    title_overlap = len(resume_tokens & title_tokens)
    title_score = min(1.0, title_overlap / max(1, len(title_tokens))) if title_tokens else 0.0

    # Domain overlap: shared professional vocabulary between resume and job profile.
    domain_overlap = len(resume_terms & profile_terms) / max(1, len(profile_terms))

    # Education relevance: related discipline or degree level matters more than exact wording.
    education_tokens = set(_normalize_routing_text(profile.requirements.required_education or "").split())
    related_education_tokens = {
        "medical", "biomedical", "laboratory", "diagnostic", "healthcare", "nursing", "science",
        "business", "administration", "management", "accounting", "finance", "hospitality",
    }
    education_present = bool(resume_tokens & (education_tokens | related_education_tokens))
    education_score = 1.0 if education_present and domain_overlap > 0 else 0.0

    # Experience/responsibility indicators reflect professional trajectory and true relevance.
    experience_indicators = {
        "experience", "experienced", "worked", "responsible", "duties", "responsibilities", "years",
        "managed", "supervised", "coordinated", "led", "operations", "administrative", "customer", "clinical", "laboratory", "diagnostic", "testing", "support",
    }
    experience_score = 1.0 if bool(resume_tokens & experience_indicators) and domain_overlap > 0 else 0.0

    # Skill overlap is a contributing signal but not the sole relevance determinant.
    required_skills = set(_normalize_routing_text(" ".join(profile.requirements.required_skills)).split()) if profile.requirements.required_skills else set()
    skill_score = len(resume_tokens & required_skills) / max(1, len(required_skills)) if required_skills else 0.0

    weighted = (
        0.35 * title_score +
        0.25 * domain_overlap +
        0.20 * experience_score +
        0.10 * education_score +
        0.10 * skill_score
    )

    # Prevent single keyword hits from deciding relevance alone.
    if title_score < 0.1 and domain_overlap < 0.15 and education_score < 0.1 and experience_score < 0.1:
        return 0.0

    return round(min(1.0, weighted), 3)


def _route_resume_to_job_profiles(resume_text: str, profiles: list[JobOpeningProfile]) -> tuple[list[JobOpeningProfile], bool]:
    if not profiles:
        return [], False

    scored_profiles = [(profile, _semantic_profile_score(resume_text, profile)) for profile in profiles]
    scored_profiles.sort(key=lambda item: item[1], reverse=True)

    best_profile, best_score = scored_profiles[0]
    if best_score < 0.18:
        return [], True

    # Preserve cases where the resume is clearly relevant to a non-nursing profile.
    if len(scored_profiles) == 1:
        return [best_profile], False

    second_profile, second_score = scored_profiles[1]
    if second_score >= max(0.3, best_score * 0.6):
        return [best_profile, second_profile], False
    return [best_profile], False


def _routing_reject_result(file_id: str, file_name: str, candidate_name: str = "Unknown") -> ResumeResult:
    return ResumeResult(
        file_id=file_id,
        file_name=file_name,
        candidate_name=candidate_name,
        decision=Decision.REJECT,
        summary="The resume did not show a clear match to any detected job opening.",
        match_score=0,
        routed_job_titles=[],
    )


def _select_best_result(results: list[tuple[JobRequirements | None, ResumeResult]]) -> tuple[JobRequirements | None, ResumeResult]:
    def rank(item: tuple[JobRequirements | None, ResumeResult]) -> tuple[float, int]:
        requirements, result = item
        score = result.match_score if result.match_score is not None else 0.0
        decision_weight = {
            Decision.ACCEPT: 3,
            Decision.DOUBTFUL: 2,
            Decision.REJECT: 1,
        }.get(result.decision, 0)
        return (score, decision_weight)

    return max(results, key=rank)


def _attach_routing_context(result: ResumeResult, routed_job_titles: list[str] | None) -> ResumeResult:
    titles = [title for title in (routed_job_titles or []) if title]
    return result.model_copy(update={"routed_job_titles": titles})


async def _evaluate_resume_for_requirements(
    job: JobState,
    text: str,
    file_name: str,
    file_id: str,
    requirements: JobRequirements | None,
    routed_job_titles: list[str] | None = None,
) -> ResumeResult:
    primary_provider = get_ai_provider()
    try:
        result = await primary_provider.evaluate_resume(
            text,
            file_name,
            file_id,
            requirements=requirements,
            recruitment_document_text=(job.recruitment_document_context.document_text if job.recruitment_document_context else ""),
        )
        return _attach_routing_context(_finalize_result(result, requirements), routed_job_titles)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Primary provider failed for %s: %s", file_name, exc)
        fallback = get_fallback_provider(primary_provider)
        if fallback is primary_provider:
            return _error_result(file_id, file_name, str(exc))

        try:
            result = await fallback.evaluate_resume(
                text,
                file_name,
                file_id,
                requirements=requirements,
                recruitment_document_text=(job.recruitment_document_context.document_text if job.recruitment_document_context else ""),
            )
            return _attach_routing_context(_finalize_result(result, requirements), routed_job_titles)
        except Exception as fallback_exc:  # noqa: BLE001
            logger.warning("Fallback provider also failed for %s: %s", file_name, fallback_exc)
            return _error_result(file_id, file_name, str(fallback_exc))


async def process_single_resume(job: JobState, file_path: Path, file_name: str) -> ResumeResult:
    """Extract text, evaluate with the AI provider, and return a result (never raises)."""
    file_id = str(uuid.uuid4())
    try:
        text = await asyncio.to_thread(extract_text, file_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Resume text extraction failed for %s: %s", file_name, exc)
        return _error_result(file_id, file_name, str(exc))

    job_profiles = job.job_profiles
    if not job_profiles and job.requirements is not None:
        job_profiles = [JobOpeningProfile(title=job.requirements.job_role or "General Professional Role", requirements=job.requirements)]

    if job_profiles:
        selected_profiles, reject = _route_resume_to_job_profiles(text, job_profiles)
        if reject:
            return _routing_reject_result(file_id, file_name)

        if len(selected_profiles) == 1:
            requirements = selected_profiles[0].requirements
            return await _evaluate_resume_for_requirements(
                job,
                text,
                file_name,
                file_id,
                requirements,
                routed_job_titles=[selected_profiles[0].title],
            )

        candidates: list[tuple[JobRequirements | None, ResumeResult]] = []
        for profile in selected_profiles:
            requirements = profile.requirements
            result = await _evaluate_resume_for_requirements(
                job,
                text,
                file_name,
                file_id,
                requirements,
                routed_job_titles=[profile.title for profile in selected_profiles],
            )
            candidates.append((requirements, result))

        _, best_result = _select_best_result(candidates)
        return best_result

    return await _evaluate_resume_for_requirements(
        job,
        text,
        file_name,
        file_id,
        job.requirements,
        routed_job_titles=[profile.title for profile in job.job_profiles] if job.job_profiles else None,
    )


def _validate_match_score_from_reasoning(match_score: float | None, reasoning: str | None) -> float | None:
    # If the model provided an explicit numeric match_score, trust it as authoritative
    # (do not modify it based on the narrative). Only derive a score from reasoning
    # when match_score is missing.
    if match_score is not None:
        try:
            return float(match_score)
        except (TypeError, ValueError):
            return None

    # No numeric score supplied — try to extract an explicit numeric mention from the reasoning
    text = (reasoning or "")
    if text:
        m = re.search(r"(?:match\s*score|score)\s*(?:is|=|:)\s*(\d{1,3})", text, flags=re.IGNORECASE)
        if m:
            try:
                return float(int(m.group(1)))
            except (TypeError, ValueError):
                pass
        # Fall back to heuristic scoring from the narrative
        return score_from_reasoning(text)
    return None


def _finalize_result(result: ResumeResult, requirements: JobRequirements | None) -> ResumeResult:
    """Classify the result.

    Priority order:
    1. If business rules say hard REJECT (policy violation), always reject.
    2. Otherwise, classify by match_score: >=80 ACCEPT, >=50 DOUBTFUL, <50 REJECT.
    """
    # Reconcile extracted structured fields against the natural-language summary
    from app.decision_utils import reconcile_extracted_fields

    normalized_exp, normalized_skills_match, normalized_edu = reconcile_extracted_fields(
        result.summary, result.experience_years, result.skills_match, result.education_level
    )

    # If requirements are provided, build AI payload and allow deterministic policy gates.
    if requirements is not None:
        edu = (normalized_edu or result.education_level or "").strip()
        edu_norm = edu.lower() if edu else "none"
        if not edu:
            education_relevant = None
        elif edu_norm in {"unknown", "n/a", "null"}:
            education_relevant = None
        elif edu_norm == "none":
            education_relevant = False
        else:
            education_relevant = True

        exp_years = normalized_exp if normalized_exp is not None else (result.experience_years if result.experience_years is not None else None)
        experience_relevant = None if exp_years is None else exp_years > 0

        # Preserve explicit model signal for skills_match unless reconciled to True/False
        skills_match_value = normalized_skills_match if normalized_skills_match is not None else result.skills_match

        ai_payload = {
            "education_level": edu_norm,
            "education_relevant": education_relevant,
            "experience_years": exp_years,
            "experience_relevant": experience_relevant,
            # Preserve explicit model signal for skills_match (can be True/False/None), reconciled above.
            "skills_match": skills_match_value,
            "reason": result.summary,
            "skills_summary": result.summary,
        }
        rules_decision, _ = apply_business_rules(requirements, ai_payload)
        if rules_decision == Decision.REJECT:
            # Hard policy gate — candidate violates a recruiter-defined constraint
            if result.decision != Decision.REJECT:
                return result.model_copy(update={"decision": Decision.REJECT})
            return result

    # Step 2 — the final authoritative score is the model-provided `match_score` when present.
    # We will not mutate the original numeric score. If it's missing, derive it from reasoning.
    # Also sanitize the reasoning so it does not contain an explicit numeric score that
    # contradicts the authoritative `match_score`.
    def _sanitize_reasoning_for_score(text: str | None, authoritative_score: float | None) -> str | None:
        if not text:
            return text
        s = text
        # Remove explicit 'match score is X' or 'score: X' mentions to avoid contradictions.
        s = re.sub(r"(?:match\s*score|score)\s*(?:is|=|:)\s*\d{1,3}", "", s, flags=re.IGNORECASE)
        # Collapse multiple spaces and stray punctuation from removals.
        s = re.sub(r"\s{2,}", " ", s).strip()
        return s

    authoritative = _validate_match_score_from_reasoning(result.match_score, result.summary)
    sanitized_summary = _sanitize_reasoning_for_score(result.summary, authoritative)

    final_decision = classify_by_match_score(
        authoritative,
        result.decision,
        requirements,
        reasoning=sanitized_summary,
    )

    updates: dict[str, object] = {}
    # Do NOT change match_score here — keep the model's numeric signal as the final authority.
    if final_decision != result.decision:
        updates["decision"] = final_decision
    if sanitized_summary is not None and sanitized_summary != result.summary:
        updates["summary"] = sanitized_summary

    # Include reconciled structured fields so outputs don't contradict the summary.
    # Experience: if reconciled to None but original was 0, set to None.
    if normalized_exp is not None and normalized_exp != result.experience_years:
        updates["experience_years"] = normalized_exp
    elif normalized_exp is None and result.experience_years == 0:
        updates["experience_years"] = None

    # Skills match: update if reconciliation produced a definitive value different from original.
    if normalized_skills_match is not None and normalized_skills_match != result.skills_match:
        updates["skills_match"] = normalized_skills_match

    # Education level: prefer reconciled detected education when it provides a value.
    if normalized_edu and (normalized_edu != result.education_level):
        updates["education_level"] = normalized_edu

    if not updates:
        return result
    return result.model_copy(update=updates)


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