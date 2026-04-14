from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.models.api import ScriptJobRequest, ScriptJobResult


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobLogEntry(BaseModel):
    id: str
    type: str
    message: str
    timestamp: str
    details: str | None = None


@dataclass
class JobRecord:
    job_id: str
    request: ScriptJobRequest
    temp_dir: Path
    file_paths: list[Path]
    status: JobStatus = JobStatus.queued
    progress: int = 0
    result: ScriptJobResult | None = None
    error: str | None = None
    logs: list[JobLogEntry] = field(default_factory=list)
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def add_log(self, log_type: str, message: str, details: str | None = None) -> None:
        self.logs.append(
            JobLogEntry(
                id=f"{self.job_id}-{len(self.logs) + 1}",
                type=log_type,
                message=message,
                timestamp=datetime.now().strftime("%H:%M:%S"),
                details=details,
            )
        )
        self.touch()

    def set_progress(self, value: int) -> None:
        self.progress = max(0, min(100, value))
        self.touch()


JobLogger = Callable[[str, str, str | None], None]
