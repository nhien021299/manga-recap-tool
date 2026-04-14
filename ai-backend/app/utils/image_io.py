from __future__ import annotations

import base64
from pathlib import Path


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")
