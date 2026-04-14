import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.deps import get_app_settings, get_job_queue
from app.models.api import CreateJobResponse, JobStatusResponse, ScriptJobRequest
from app.models.jobs import JobRecord, JobStatus
from app.utils.temp_files import save_uploads

router = APIRouter(prefix="/script", tags=["script"])


@router.post("/jobs", response_model=CreateJobResponse)
async def create_script_job(
    context: str = Form(...),
    panels: str = Form(...),
    options: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    settings=Depends(get_app_settings),
    job_queue=Depends(get_job_queue),
) -> CreateJobResponse:
    request = ScriptJobRequest(
        context=json.loads(context),
        panels=json.loads(panels),
        options=json.loads(options) if options else {},
    )
    if len(request.panels) != len(files):
        raise HTTPException(status_code=400, detail="Panel metadata count must match uploaded files.")

    job_id = str(uuid.uuid4())
    temp_dir, saved_paths = await save_uploads(settings.temp_root, job_id, files)
    job = JobRecord(job_id=job_id, request=request, temp_dir=temp_dir, file_paths=saved_paths)
    job.add_log("request", f"Queued script job for {len(request.panels)} panels")
    await job_queue.enqueue(job)
    return CreateJobResponse(jobId=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_script_job(job_id: str, job_queue=Depends(get_job_queue)) -> JobStatusResponse:
    job = job_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(
        jobId=job.job_id,
        status=job.status,
        progress=job.progress,
        error=job.error,
        logs=job.logs,
    )


@router.get("/jobs/{job_id}/result")
async def get_script_job_result(job_id: str, job_queue=Depends(get_job_queue)):
    job = job_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != JobStatus.completed or job.result is None:
        raise HTTPException(status_code=409, detail="Job result is not ready.")
    return job.result


@router.post("/jobs/{job_id}/cancel", response_model=JobStatusResponse)
async def cancel_script_job(job_id: str, job_queue=Depends(get_job_queue)) -> JobStatusResponse:
    job = await job_queue.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(
        jobId=job.job_id,
        status=job.status,
        progress=job.progress,
        error=job.error,
        logs=job.logs,
    )
