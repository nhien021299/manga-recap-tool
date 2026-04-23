from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.deps import get_render_queue, get_render_service
from app.main import app
from app.models.api import RenderClipSpec, RenderPlanRequest
from app.models.render_jobs import RenderJobRecord, RenderJobStatus


class DummyRenderService:
    def __init__(self, tmp_path: Path, available: bool = True) -> None:
        self.tmp_path = tmp_path
        self.available = available

    def assert_available(self) -> str:
        if not self.available:
            raise FileNotFoundError("ffmpeg missing")
        return "ffmpeg"

    async def prepare_job(self, job_id: str, plan: RenderPlanRequest, clips: list[RenderClipSpec], files):
        self.assert_available()
        if len(files) != 2:
            raise ValueError("Missing uploaded render assets for keys: panel-1, audio-1")
        job_dir = self.tmp_path / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return RenderJobRecord(
            job_id=job_id,
            plan=plan,
            clips=clips,
            temp_dir=job_dir,
            asset_files={"panel-1": job_dir / "panel-1.png", "audio-1": job_dir / "audio-1.wav"},
            output_path=job_dir / "output.mp4",
        )

    def build_download_url(self, job_id: str) -> str:
        return f"/api/v1/render/jobs/{job_id}/result"


class DummyRenderQueue:
    def __init__(self, job: RenderJobRecord | None = None) -> None:
        self.job = job
        self.jobs: dict[str, RenderJobRecord] = {}
        if job is not None:
            self.jobs[job.job_id] = job

    async def enqueue(self, job: RenderJobRecord):
        self.jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> RenderJobRecord | None:
        return self.jobs.get(job_id)

    async def cancel(self, job_id: str) -> RenderJobRecord | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        job.status = RenderJobStatus.cancelled
        job.error = "Render cancelled by user."
        return job


def _build_payload():
    return {
        "plan": json.dumps(
            {
                "outputWidth": 1080,
                "outputHeight": 1920,
                "captionMode": "burned",
                "frameRate": 30,
            }
        ),
        "clips": json.dumps(
            [
                {
                    "clipId": "clip-1",
                    "panelId": "panel-1",
                    "orderIndex": 0,
                    "durationMs": 2400,
                    "holdAfterMs": 250,
                    "captionText": "Narration",
                    "panelFileKey": "panel-1",
                    "audioFileKey": "audio-1",
                }
            ]
        ),
    }


def test_render_job_create_route_returns_queued(tmp_path: Path):
    render_service = DummyRenderService(tmp_path)
    render_queue = DummyRenderQueue()
    app.dependency_overrides[get_render_service] = lambda: render_service
    app.dependency_overrides[get_render_queue] = lambda: render_queue

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/render/jobs",
                data=_build_payload(),
                files=[
                    ("files", ("panel-1.png", b"panel", "image/png")),
                    ("files", ("audio-1.wav", b"audio", "audio/wav")),
                ],
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "queued"
        assert payload["jobId"]
    finally:
        app.dependency_overrides.clear()


def test_render_job_create_route_rejects_mismatched_assets(tmp_path: Path):
    render_service = DummyRenderService(tmp_path)
    render_queue = DummyRenderQueue()
    app.dependency_overrides[get_render_service] = lambda: render_service
    app.dependency_overrides[get_render_queue] = lambda: render_queue

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/render/jobs",
                data=_build_payload(),
                files=[("files", ("panel-1.png", b"panel", "image/png"))],
            )
        assert response.status_code == 400
        assert "Missing uploaded render assets" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_render_job_create_route_returns_503_when_ffmpeg_missing(tmp_path: Path):
    render_service = DummyRenderService(tmp_path, available=False)
    render_queue = DummyRenderQueue()
    app.dependency_overrides[get_render_service] = lambda: render_service
    app.dependency_overrides[get_render_queue] = lambda: render_queue

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/render/jobs",
                data=_build_payload(),
                files=[
                    ("files", ("panel-1.png", b"panel", "image/png")),
                    ("files", ("audio-1.wav", b"audio", "audio/wav")),
                ],
            )
        assert response.status_code == 503
        assert response.json()["detail"] == "ffmpeg missing"
    finally:
        app.dependency_overrides.clear()


def test_render_result_route_requires_completed_job(tmp_path: Path):
    job_dir = tmp_path / "job-1"
    job_dir.mkdir(parents=True, exist_ok=True)
    job = RenderJobRecord(
        job_id="job-1",
        plan=RenderPlanRequest(outputWidth=1080, outputHeight=1920, captionMode="off", frameRate=30),
        clips=[],
        temp_dir=job_dir,
        asset_files={},
        output_path=job_dir / "output.mp4",
    )
    job.status = RenderJobStatus.running

    render_service = DummyRenderService(tmp_path)
    render_queue = DummyRenderQueue(job)
    app.dependency_overrides[get_render_service] = lambda: render_service
    app.dependency_overrides[get_render_queue] = lambda: render_queue

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/render/jobs/job-1/result")
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_render_result_route_streams_mp4_when_completed(tmp_path: Path):
    job_dir = tmp_path / "job-2"
    job_dir.mkdir(parents=True, exist_ok=True)
    output_path = job_dir / "output.mp4"
    output_path.write_bytes(b"fake-mp4")
    job = RenderJobRecord(
        job_id="job-2",
        plan=RenderPlanRequest(outputWidth=1080, outputHeight=1920, captionMode="off", frameRate=30),
        clips=[],
        temp_dir=job_dir,
        asset_files={},
        output_path=output_path,
    )
    job.status = RenderJobStatus.completed

    render_service = DummyRenderService(tmp_path)
    render_queue = DummyRenderQueue(job)
    app.dependency_overrides[get_render_service] = lambda: render_service
    app.dependency_overrides[get_render_queue] = lambda: render_queue

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/render/jobs/job-2/result")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("video/mp4")
        assert response.content == b"fake-mp4"
    finally:
        app.dependency_overrides.clear()
