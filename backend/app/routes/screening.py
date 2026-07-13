"""API routes for the resume screening workflow."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models.schemas import StartScreeningResponse, WSEvent, WSEventType
from app.services.resume_service import (
    job_manager,
    run_screening_job,
    save_uploads_to_temp,
)
from pathlib import Path

from app.utils.csv_export import build_export_archive, results_to_csv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.post("/start", response_model=StartScreeningResponse)
async def start_screening(files: list[UploadFile]) -> StartScreeningResponse:
    settings = get_settings()

    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

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

    job = job_manager.create_job(total_files=len(valid_files))
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


@router.get("/export-folders/{job_id}")
async def export_folders(job_id: str) -> StreamingResponse:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    file_map: dict[str, Path] = {}
    if job.temp_dir:
        for path in job.temp_dir.iterdir():
            file_map[path.name] = path

    archive_bytes = build_export_archive(job.results, file_map)
    return StreamingResponse(
        iter([archive_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="screening_results_{job_id[:8]}.zip"'},
    )
