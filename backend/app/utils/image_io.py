from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image


def image_to_base64(path: Path, *, max_width: int | None = None, max_height: int | None = None) -> str:
    if not max_width and not max_height:
        return base64.b64encode(path.read_bytes()).decode("utf-8")

    with Image.open(path) as image:
        processed = image.convert("RGB")
        original_width, original_height = processed.size
        target_width = max_width or original_width
        target_height = max_height or original_height

        if original_width > target_width or original_height > target_height:
            resized = processed.copy()
            resized.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            processed = resized

        output = BytesIO()
        processed.save(output, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(output.getvalue()).decode("utf-8")
