from pathlib import Path

import pytest

from app.models.api import ScriptJobRequest, ScriptJobResult
from app.models.domain import Metrics, RawOutputs, ScriptContext
from app.models.jobs import JobRecord, JobStatus
from app.services.job_queue import JobQueue


class DummyPipeline:
    async def run_job(self, _job):
        return ScriptJobResult(
            understandings=[],
            generatedItems=[],
            storyMemories=[],
            panelSignature="sig",
            rawOutputs=RawOutputs(),
            metrics=Metrics(panelCount=0, totalMs=0, captionMs=0, scriptMs=0),
        )


@pytest.mark.asyncio
async def test_queue_marks_job_completed(tmp_path: Path):
    queue = JobQueue(DummyPipeline())
    await queue.start()
    try:
        job = JobRecord(
            job_id="job-1",
            request=ScriptJobRequest(context=ScriptContext(mangaName="A", mainCharacter="B"), panels=[]),
            temp_dir=tmp_path / "job-1",
            file_paths=[],
        )
        await queue.enqueue(job)
        await queue._queue.join()
        assert job.status == JobStatus.completed
    finally:
        await queue.stop()
