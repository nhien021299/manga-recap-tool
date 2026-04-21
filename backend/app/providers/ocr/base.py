from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.models.domain import OCRResult


class OCRProvider(Protocol):
    async def extract(self, image_path: Path, panel_id: str) -> OCRResult:
        ...
