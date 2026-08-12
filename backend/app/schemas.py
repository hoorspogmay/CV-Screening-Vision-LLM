"""Pydantic models shared across the API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from app.job_requirements import JobOpeningProfile
from pydantic import BaseModel, Field


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    DOUBTFUL = "DOUBTFUL"
    REJECT = "REJECT"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"


class ResumeResult(BaseModel):
    file_id: str
    file_name: str
    candidate_name: str
    decision: Decision
    summary: str
    error: Optional[str] = None
    match_score: Optional[float] = Field(default=None, ge=0, le=100)
    routed_job_titles: list[str] = Field(default_factory=list)
    # Structured fields used by job_rules.py for deterministic policy checks
    education_level: Optional[str] = None
    experience_years: Optional[int] = None
    skills_match: Optional[bool] = None


class JobProgress(BaseModel):
    job_id: str
    status: JobStatus
    total: int
    processed: int
    accepted: int
    doubtful: int
    rejected: int
    failed: int


class StartScreeningResponse(BaseModel):
    job_id: str
    total_files: int
    job_profiles: list[JobOpeningProfile] = Field(default_factory=list)


class WSEventType(str, Enum):
    PROGRESS = "progress"
    RESULT = "result"
    ERROR = "error"
    DONE = "done"


class WSEvent(BaseModel):
    type: WSEventType
    progress: Optional[JobProgress] = None
    result: Optional[ResumeResult] = None
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)