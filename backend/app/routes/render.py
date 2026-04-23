from __future__ import annotations

import json
import subprocess
import sys
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.deps import get_render_queue, get_render_service
from app.models.api import (
    RenderClipSpec,
    RenderJobCreateResponse,
    RenderRevealResponse,
    RenderJobStatusResponse,
    RenderPlanRequest,
)
from app.models.render_jobs import RenderJobRecord, RenderJobStatus

router = APIRouter(prefix="/render", tags=["render"])


def _build_status_response(job: RenderJobRecord, render_service) -> RenderJobStatusResponse:
    return RenderJobStatusResponse(
        jobId=job.job_id,
        status=job.status,
        progress=job.progress,
        phase=job.phase,
        detail=job.detail,
        downloadUrl=render_service.build_download_url(job.job_id) if job.status == RenderJobStatus.completed else None,
        error=job.error,
        logs=job.logs,
    )


@router.post("/jobs", response_model=RenderJobCreateResponse)
async def create_render_job(
    plan: str = Form(...),
    clips: str = Form(...),
    files: list[UploadFile] = File(...),
    render_service=Depends(get_render_service),
    render_queue=Depends(get_render_queue),
) -> RenderJobCreateResponse:
    try:
        render_plan = RenderPlanRequest(**json.loads(plan))
        render_clips = [RenderClipSpec(**item) for item in json.loads(clips)]
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid render job payload: {exc}") from exc

    job_id = str(uuid.uuid4())

    try:
        job = await render_service.prepare_job(job_id=job_id, plan=render_plan, clips=render_clips, files=files)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await render_queue.enqueue(job)
    return RenderJobCreateResponse(jobId=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=RenderJobStatusResponse)
async def get_render_job_status(
    job_id: str,
    render_service=Depends(get_render_service),
    render_queue=Depends(get_render_queue),
) -> RenderJobStatusResponse:
    job = render_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Render job not found.")
    return _build_status_response(job, render_service)


@router.get("/jobs/{job_id}/result")
async def get_render_job_result(
    job_id: str,
    render_queue=Depends(get_render_queue),
):
    job = render_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Render job not found.")
    if job.status != RenderJobStatus.completed or not job.output_path.exists():
        raise HTTPException(status_code=409, detail="Render result is not ready.")
    return FileResponse(
        path=job.output_path,
        media_type="video/mp4",
        filename=f"render-{job.job_id}.mp4",
        content_disposition_type="inline",
    )


@router.post("/jobs/{job_id}/reveal", response_model=RenderRevealResponse)
async def reveal_render_job_result(
    job_id: str,
    render_queue=Depends(get_render_queue),
) -> RenderRevealResponse:
    job = render_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Render job not found.")
    if job.status != RenderJobStatus.completed or not job.output_path.exists():
        raise HTTPException(status_code=409, detail="Render result is not ready.")
    if sys.platform != "win32":
        raise HTTPException(status_code=501, detail="Reveal result is currently supported on Windows only.")

    try:
        subprocess.Popen(["explorer.exe", "/select,", str(job.output_path)])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to open Explorer for render result: {exc}") from exc

    return RenderRevealResponse(success=True)


@router.post("/jobs/{job_id}/cancel", response_model=RenderJobStatusResponse)
async def cancel_render_job(
    job_id: str,
    render_service=Depends(get_render_service),
    render_queue=Depends(get_render_queue),
) -> RenderJobStatusResponse:
    job = await render_queue.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Render job not found.")
    return _build_status_response(job, render_service)
