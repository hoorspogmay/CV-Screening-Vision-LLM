"""API routes for the resume screening workflow."""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pathlib import Path

from app.config import get_settings
from app.schemas import StartScreeningResponse, WSEvent, WSEventType
from app.job_extraction import extract_jobs_from_recruitment_document
from app.job_requirements import (
    JobOpeningProfile,
    JobRequirements,
    build_job_profiles_from_extraction,
    build_job_profiles_from_text,
    build_job_requirements_from_text,
)
from app.file_utils import extract_text
from app.resume_service import (
    RecruitmentDocumentContext,
    job_manager,
    run_screening_job,
    save_uploads_to_temp,
)
from app.csv_export import results_to_csv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.post("/start", response_model=StartScreeningResponse)
async def start_screening(
    files: list[UploadFile] = File(...),
    job_spec: UploadFile | None = File(default=None),
) -> StartScreeningResponse:
    settings = get_settings()

    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    parsed_requirements: JobRequirements | None = None
    job_profiles: list[JobOpeningProfile] = []
    recruitment_document_context: RecruitmentDocumentContext | None = None
    if job_spec is not None:
        filename = job_spec.filename or ""
        if not filename.lower().endswith(".docx"):
            raise HTTPException(status_code=400, detail="Job specification must be a .docx Word file.")

        spec_bytes = await job_spec.read()
        if len(spec_bytes) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Job specification file exceeds the upload size limit.")

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
            handle.write(spec_bytes)
            temp_spec_path = Path(handle.name)

        try:
            spec_text = extract_text(temp_spec_path)
        finally:
            temp_spec_path.unlink(missing_ok=True)

        parsed_requirements = build_job_requirements_from_text(spec_text)
        recruitment_document_context = RecruitmentDocumentContext(spec_text)

        try:
            extracted_jobs = await extract_jobs_from_recruitment_document(spec_text)
        except Exception as exc:
            logger.warning("Job extraction failed, falling back to rule-based parsing: %s", exc)
            extracted_jobs = []

        if extracted_jobs:
            job_profiles = build_job_profiles_from_extraction(extracted_jobs)
        else:
            job_profiles = build_job_profiles_from_text(spec_text)
            if not job_profiles and parsed_requirements is not None:
                job_profiles = [JobOpeningProfile(title=parsed_requirements.job_role or "General Professional Role", requirements=parsed_requirements)]

    valid_files: list[tuple[str, bytes]] = []
    for upload in files:
        suffix = "." + upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
        if suffix not in settings.allowed_extensions:
            continue  # silently skip unsupported files (e.g. .DS_Store from folder upload)
        content = await upload.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            continue
        valid_files.append((upload.filename, content))

    if not valid_files:
        raise HTTPException(
            status_code=400,
            detail="No valid PDF or DOCX resumes found in the upload.",
        )

    job = job_manager.create_job(
        total_files=len(valid_files),
        requirements=parsed_requirements,
        recruitment_document_context=recruitment_document_context,
        job_profiles=job_profiles if job_spec is not None else None,
    )
    temp_dir, saved_paths = save_uploads_to_temp(valid_files)
    job.temp_dir = temp_dir

    # Fire the batch off in the background; the client tracks progress over WebSocket.
    asyncio.create_task(run_screening_job(job, saved_paths))

    return StartScreeningResponse(job_id=job.job_id, total_files=job.total)


@router.websocket("/ws/{job_id}")
async def screening_updates(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()

    job = job_manager.get_job(job_id)
    if job is None:
        await websocket.send_json(
            WSEvent(
                type=WSEventType.ERROR,
                message=f"Job '{job_id}' was not found. Refresh the page and start a new screening job.",
            ).model_dump(mode="json")
        )
        await websocket.close(code=4404)
        return

    queue = job_manager.subscribe(job)

    try:
        # Replay current state immediately so a client connecting mid-job (or
        # reconnecting) isn't stuck looking at an empty screen.
        for result in job.results:
            await websocket.send_json(WSEvent(type=WSEventType.RESULT, result=result).model_dump(mode="json"))
        await websocket.send_json(WSEvent(type=WSEventType.PROGRESS, progress=job.progress()).model_dump(mode="json"))
        if job.status == "completed":
            await websocket.send_json(WSEvent(type=WSEventType.DONE, progress=job.progress()).model_dump(mode="json"))

        while True:
            event: WSEvent = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
            if event.type == WSEventType.DONE:
                break
    except WebSocketDisconnect:
        pass
    finally:
        job_manager.unsubscribe(job, queue)


@router.get("/export/{job_id}")
async def export_csv(job_id: str) -> StreamingResponse:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    csv_content = results_to_csv(job.results)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="screening_results_{job_id[:8]}.csv"'},
    )

