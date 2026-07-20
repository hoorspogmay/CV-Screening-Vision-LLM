"""Pydantic models shared across the API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

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
    skills_summary: str
    education_summary: str
    experience_summary: str
    reason: str
    error: Optional[str] = None
    match_score: Optional[float] = Field(default=None, ge=0, le=100)
    education_level: Optional[str] = None
    education_relevant: Optional[bool] = None
    experience_years: Optional[int] = None
    experience_relevant: Optional[bool] = None
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
