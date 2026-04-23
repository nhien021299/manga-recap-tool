from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from subprocess import Popen
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.models.api import RenderClipSpec, RenderPlanRequest


class RenderJobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RenderJobLogEntry(BaseModel):
    id: str
    type: str
    message: str
    timestamp: str
    details: str | None = None


@dataclass
class RenderJobRecord:
    job_id: str
    plan: RenderPlanRequest
    clips: list[RenderClipSpec]
    temp_dir: Path
    asset_files: dict[str, Path]
    output_path: Path
    status: RenderJobStatus = RenderJobStatus.queued
    progress: int = 0
    phase: str = "accepted"
    detail: str | None = "Waiting for render worker."
    error: str | None = None
    logs: list[RenderJobLogEntry] = field(default_factory=list)
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    current_process: Popen[bytes] | None = None

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def add_log(self, log_type: str, message: str, details: str | None = None) -> None:
        self.logs.append(
            RenderJobLogEntry(
                id=f"{self.job_id}-render-{len(self.logs) + 1}",
                type=log_type,
                message=message,
                timestamp=datetime.now().strftime("%H:%M:%S"),
                details=details,
            )
        )
        self.touch()

    def set_progress(self, value: int, phase: str | None = None, detail: str | None = None) -> None:
        self.progress = max(0, min(100, value))
        if phase is not None:
            self.phase = phase
        self.detail = detail
        self.touch()

    def mark_completed(self, ttl_seconds: int) -> None:
        self.status = RenderJobStatus.completed
        self.progress = 100
        self.phase = "completed"
        self.detail = "MP4 ready."
        self.completed_at = datetime.now(timezone.utc)
        self.expires_at = self.completed_at + timedelta(seconds=max(1, ttl_seconds))
        self.touch()

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = now or datetime.now(timezone.utc)
        return current >= self.expires_at
