from __future__ import annotations

import asyncio
from contextlib import suppress

from app.models.render_jobs import RenderJobRecord, RenderJobStatus


class RenderJobQueue:
    def __init__(self, render_service) -> None:
        self.render_service = render_service
        self.jobs: dict[str, RenderJobRecord] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._worker_task
        self._worker_task = None

    async def enqueue(self, job: RenderJobRecord) -> RenderJobRecord:
        self._cleanup_expired_jobs()
        self.jobs[job.job_id] = job
        await self._queue.put(job.job_id)
        return job

    def get(self, job_id: str) -> RenderJobRecord | None:
        self._cleanup_expired_jobs()
        return self.jobs.get(job_id)

    async def cancel(self, job_id: str) -> RenderJobRecord | None:
        self._cleanup_expired_jobs()
        job = self.jobs.get(job_id)
        if job is None:
            return None

        job.cancel_requested = True
        if job.status == RenderJobStatus.queued:
            job.status = RenderJobStatus.cancelled
            job.error = "Render cancelled by user."
            job.set_progress(job.progress, phase="cancelled", detail="Cancelled before processing started.")
            job.add_log("request", "Render cancelled before worker execution.")
            self.render_service.finalize_job(job)
        elif job.status == RenderJobStatus.running:
            job.set_progress(job.progress, phase="cancelling", detail="Stopping native ffmpeg process.")
            job.add_log("request", "Render cancellation requested.")
            await self.render_service.cancel_running_job(job)
        job.touch()
        return job

    def _cleanup_expired_jobs(self) -> None:
        expired_ids = [job_id for job_id, job in self.jobs.items() if self.render_service.expire_job(job)]
        for job_id in expired_ids:
            self.jobs.pop(job_id, None)

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self.jobs.get(job_id)
            if job is None or job.status == RenderJobStatus.cancelled:
                self._queue.task_done()
                continue

            try:
                if job.cancel_requested:
                    job.status = RenderJobStatus.cancelled
                    job.error = "Render cancelled by user."
                    job.set_progress(job.progress, phase="cancelled", detail="Cancelled before processing started.")
                    continue

                job.status = RenderJobStatus.running
                job.set_progress(4, phase="accepted", detail="Render worker accepted the job.")
                await self.render_service.render(job)

                if job.cancel_requested:
                    job.status = RenderJobStatus.cancelled
                    job.error = "Render cancelled by user."
                    job.set_progress(job.progress, phase="cancelled", detail="Cancelled during render.")
                else:
                    job.mark_completed(self.render_service.settings.render_result_ttl_seconds)
            except Exception as exc:
                exc_text = str(exc).strip() or repr(exc)
                if job.cancel_requested or "cancelled by user" in str(exc).lower():
                    job.status = RenderJobStatus.cancelled
                    job.error = "Render cancelled by user."
                    job.set_progress(job.progress, phase="cancelled", detail="Cancelled during render.")
                else:
                    job.status = RenderJobStatus.failed
                    job.error = exc_text
                    job.set_progress(job.progress, phase="failed", detail=exc_text)
                    job.add_log("error", "Backend render failed.", exc_text)
            finally:
                self.render_service.finalize_job(job)
                job.touch()
                self._queue.task_done()
