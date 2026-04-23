from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models.api import RenderPlanRequest
from app.models.render_jobs import RenderJobRecord, RenderJobStatus
from app.services.render_queue import RenderJobQueue


class DummyRenderService:
    def __init__(self) -> None:
        self.settings = type("Settings", (), {"render_result_ttl_seconds": 3600})()

    async def render(self, job: RenderJobRecord) -> None:
        job.set_progress(50, phase="rendering clip 1/1", detail="Rendering clip 1/1")
        await asyncio.sleep(0.01)
        job.output_path.write_bytes(b"fake-mp4")

    async def cancel_running_job(self, job: RenderJobRecord) -> None:
        job.cancel_requested = True

    def finalize_job(self, job: RenderJobRecord) -> None:
        if job.status == RenderJobStatus.completed:
            return
        if job.temp_dir.exists():
            for child in job.temp_dir.iterdir():
                child.unlink(missing_ok=True)
            job.temp_dir.rmdir()

    def expire_job(self, job: RenderJobRecord) -> bool:
        if not job.is_expired():
            return False
        if job.temp_dir.exists():
            for child in job.temp_dir.iterdir():
                child.unlink(missing_ok=True)
            job.temp_dir.rmdir()
        return True


class SlowRenderService(DummyRenderService):
    async def render(self, job: RenderJobRecord) -> None:
        job.set_progress(45, phase="rendering clip 1/2", detail="Rendering clip 1/2")
        while not job.cancel_requested:
            await asyncio.sleep(0.01)
        raise RuntimeError("Render cancelled by user.")


def build_render_job(tmp_path: Path, job_id: str) -> RenderJobRecord:
    job_dir = tmp_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return RenderJobRecord(
        job_id=job_id,
        plan=RenderPlanRequest(outputWidth=1080, outputHeight=1920, captionMode="off", frameRate=30),
        clips=[],
        temp_dir=job_dir,
        asset_files={},
        output_path=job_dir / "output.mp4",
    )


@pytest.mark.asyncio
async def test_render_queue_marks_job_completed(tmp_path: Path):
    queue = RenderJobQueue(DummyRenderService())
    await queue.start()
    try:
        job = build_render_job(tmp_path, "render-1")
        await queue.enqueue(job)
        await queue._queue.join()
        assert job.status == RenderJobStatus.completed
        assert job.output_path.exists()
        assert job.progress == 100
    finally:
        await queue.stop()


@pytest.mark.asyncio
async def test_render_queue_cancels_running_job_and_cleans_temp_dir(tmp_path: Path):
    queue = RenderJobQueue(SlowRenderService())
    await queue.start()
    try:
        job = build_render_job(tmp_path, "render-2")
        await queue.enqueue(job)
        await asyncio.sleep(0.05)
        cancelled_job = await queue.cancel(job.job_id)
        assert cancelled_job is job
        await queue._queue.join()
        assert job.status == RenderJobStatus.cancelled
        assert not job.temp_dir.exists()
    finally:
        await queue.stop()


@pytest.mark.asyncio
async def test_render_queue_prunes_expired_completed_jobs(tmp_path: Path):
    queue = RenderJobQueue(DummyRenderService())
    job = build_render_job(tmp_path, "render-3")
    job.status = RenderJobStatus.completed
    job.completed_at = datetime.now(timezone.utc) - timedelta(hours=2)
    job.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    queue.jobs[job.job_id] = job

    assert queue.get(job.job_id) is None
