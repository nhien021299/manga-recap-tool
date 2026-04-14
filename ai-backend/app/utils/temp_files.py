from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import UploadFile


async def save_uploads(temp_root: Path, job_id: str, files: list[UploadFile]) -> tuple[Path, list[Path]]:
    job_dir = temp_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for index, file in enumerate(files):
        suffix = Path(file.filename or f"panel-{index + 1}.png").suffix or ".png"
        path = job_dir / f"panel-{index + 1:03d}{suffix}"
        path.write_bytes(await file.read())
        saved_paths.append(path)
    return job_dir, saved_paths


def cleanup_temp_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
