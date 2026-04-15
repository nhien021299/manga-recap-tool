from __future__ import annotations

import asyncio
from contextlib import suppress

from app.models.jobs import JobRecord, JobStatus
from app.utils.temp_files import cleanup_temp_dir


class JobQueue:
    def __init__(self, script_pipeline) -> None:
        self.script_pipeline = script_pipeline
        self.jobs: dict[str, JobRecord] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

    async def enqueue(self, job: JobRecord) -> JobRecord:
        self.jobs[job.job_id] = job
        await self._queue.put(job.job_id)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)

    async def cancel(self, job_id: str) -> JobRecord | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        job.cancel_requested = True
        if job.status == JobStatus.queued:
            job.status = JobStatus.cancelled
            job.error = "Job cancelled by user."
            cleanup_temp_dir(job.temp_dir)
        job.touch()
        return job

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self.jobs.get(job_id)
            if job is None or job.status == JobStatus.cancelled:
                self._queue.task_done()
                continue
            try:
                if job.cancel_requested:
                    job.status = JobStatus.cancelled
                    job.error = "Job cancelled by user."
                    continue
                job.status = JobStatus.running
                job.set_progress(10)
                result = await self.script_pipeline.run_job(job)
                if job.cancel_requested:
                    job.status = JobStatus.cancelled
                    job.error = "Job cancelled by user."
                else:
                    job.result = result
                    job.status = JobStatus.completed
                    job.set_progress(100)
            except Exception as exc:  # pragma: no cover
                if "cancelled by user" in str(exc).lower():
                    job.status = JobStatus.cancelled
                    job.error = "Job cancelled by user."
                else:
                    job.status = JobStatus.failed
                    job.error = str(exc)
                    known_error_categories = {
                        "caption raw provider error",
                        "caption JSON validation failed",
                        "caption repair failed",
                    }
                    if job.error not in known_error_categories:
                        job.add_log("error", "Backend script pipeline failed", str(exc))
            finally:
                cleanup_temp_dir(job.temp_dir)
                job.touch()
                self._queue.task_done()
