"""Video production API routes.

Provides endpoints for:
- POST /video/tts-batch: Generate TTS audio for all scenes
- POST /video/produce: Full pipeline orchestration (server-side narration path)
- POST /video/produce-from-narration: Upload narration JSON + panels → full pipeline
- GET  /video/jobs/{job_id}: Poll job status
- GET  /video/jobs/{job_id}/result: Download final video
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.deps import get_app_settings, get_video_orchestrator, get_video_tts_service
from app.models.video import (
    BatchTtsRequest,
    BatchTtsResult,
    VideoJobStatus,
    VideoProduceRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["video"])


@router.post("/tts-batch", response_model=BatchTtsResult)
async def generate_tts_batch(
    request: BatchTtsRequest,
    video_tts_service=Depends(get_video_tts_service),
) -> BatchTtsResult:
    """Generate TTS audio for all scenes in a narration package."""
    job_id = str(uuid.uuid4())
    try:
        result = await run_in_threadpool(
            video_tts_service.generate_batch,
            request,
            job_id=job_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return result


@router.post("/produce", response_model=VideoJobStatus)
async def produce_video(
    request: VideoProduceRequest,
    video_orchestrator=Depends(get_video_orchestrator),
) -> VideoJobStatus:
    """Start the full video production pipeline.

    Runs TTS → Gemini direction → Remotion render in sequence.
    Returns a job ID for polling.
    """
    try:
        job_status = await video_orchestrator.start_production(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return job_status


@router.post("/produce-from-narration", response_model=VideoJobStatus)
async def produce_from_narration(
    narration: str = Form(...),
    voice_key: str = Form(default="voice_default"),
    speed: float = Form(default=1.15),
    provider: str = Form(default="vieneu"),
    style: str = Form(default="dark_xianxia_recap"),
    width: int = Form(default=1920),
    height: int = Form(default=1080),
    fps: int = Form(default=30),
    files: list[UploadFile] = File(...),
    settings=Depends(get_app_settings),
    video_orchestrator=Depends(get_video_orchestrator),
) -> VideoJobStatus:
    """Upload narration JSON + panel images → full video production.

    Accepts a narration JSON with scenes and panel image files.
    Maps each scene to an image by order, then runs:
    TTS → Gemini video direction → Remotion render.
    Returns a job ID for polling.
    """
    try:
        narration_data = json.loads(narration)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid narration JSON: {exc}"
        ) from exc

    scenes = narration_data.get("scenes", [])
    if not scenes:
        raise HTTPException(status_code=400, detail="Narration JSON must contain a non-empty 'scenes' array.")
    if len(scenes) != len(files):
        raise HTTPException(
            status_code=400,
            detail=f"Scene count ({len(scenes)}) must match uploaded file count ({len(files)}).",
        )

    # Create job directory and save panel images
    job_id = str(uuid.uuid4())
    job_dir = settings.render_temp_root.parent / "video-jobs" / job_id
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    for i, (scene, file) in enumerate(zip(scenes, files)):
        ext = Path(file.filename or f"panel-{i}.png").suffix or ".png"
        scene_num = scene.get("scene", i + 1)
        image_path = images_dir / f"scene_{scene_num:02d}{ext}"
        content = await file.read()
        image_path.write_bytes(content)
        scene["image_path"] = str(image_path)

    # Build and save NarrationPackage JSON
    package_data = {
        "project": narration_data.get("project", "manga-recap"),
        "chapter": narration_data.get("chapter", 1),
        "language": narration_data.get("language", "vi-VN"),
        "scenes": scenes,
    }

    narration_path = job_dir / "narration.json"
    narration_path.write_text(
        json.dumps(package_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info(
        "Narration upload saved job_id=%s scenes=%d narration_path=%s",
        job_id, len(scenes), narration_path,
    )

    # Start production pipeline
    request = VideoProduceRequest(
        narration_path=str(narration_path),
        voice_key=voice_key,
        speed=speed,
        provider=provider,
        style=style,
        width=width,
        height=height,
        fps=fps,
    )

    try:
        job_status = await video_orchestrator.start_production(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return job_status


@router.get("/jobs/{job_id}", response_model=VideoJobStatus)
async def get_video_job_status(
    job_id: str,
    video_orchestrator=Depends(get_video_orchestrator),
) -> VideoJobStatus:
    """Poll the status of a video production job."""
    status = video_orchestrator.get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Video job not found.")
    return status


@router.get("/jobs/{job_id}/result")
async def get_video_job_result(
    job_id: str,
    video_orchestrator=Depends(get_video_orchestrator),
):
    """Download the final rendered video."""
    result_path = video_orchestrator.get_result_path(job_id)
    if result_path is None:
        raise HTTPException(status_code=404, detail="Video job not found or not ready.")

    return FileResponse(
        path=result_path,
        media_type="video/mp4",
        filename=f"video-{job_id}.mp4",
        content_disposition_type="inline",
    )
