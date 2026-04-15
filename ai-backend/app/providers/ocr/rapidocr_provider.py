from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from rapidocr_onnxruntime import RapidOCR

from app.models.domain import OCRLine, OCRResult


class RapidOCRProvider:
    def __init__(self, *, min_confidence: float, max_text_lines: int, prefer_sfx: bool) -> None:
        self.min_confidence = min_confidence
        self.max_text_lines = max_text_lines
        self.prefer_sfx = prefer_sfx
        self._engine = RapidOCR()

    async def extract(self, image_path: Path, panel_id: str) -> OCRResult:
        result, _elapsed = await asyncio.to_thread(self._engine, image_path)
        lines = self._normalize_lines(result or [])
        return OCRResult(
            panel_id=panel_id,
            lines=lines,
            full_text=" ".join(line.text for line in lines).strip(),
            has_text=bool(lines),
        )

    def _normalize_lines(self, raw_lines: list[list[Any]]) -> list[OCRLine]:
        lines: list[OCRLine] = []
        for raw_line in raw_lines:
            if len(raw_line) < 3:
                continue
            bbox, text, confidence = raw_line[0], str(raw_line[1]).strip(), float(raw_line[2] or 0.0)
            if not text or confidence < self.min_confidence:
                continue
            lines.append(
                OCRLine(
                    text=text,
                    confidence=confidence,
                    role=self._classify_role(text),
                    bbox=self._flatten_bbox(bbox),
                )
            )
        return lines[: self.max_text_lines]

    def _classify_role(self, text: str) -> str:
        normalized = text.strip()
        compact = normalized.replace(" ", "")
        has_space = " " in normalized
        ascii_letters = sum(char.isalpha() for char in compact)
        uppercase_ratio = (
            sum(char.isupper() for char in compact if char.isalpha()) / max(1, ascii_letters)
            if ascii_letters
            else 0.0
        )
        if self.prefer_sfx and (
            len(compact) <= 6
            or uppercase_ratio >= 0.7
            or any(char in compact for char in ("!", "?", "~", "…"))
            or ascii_letters <= 2
        ):
            return "sfx"
        if has_space or any(char in normalized for char in (".", ",", ":", ";", "\"", "'")):
            return "dialogue"
        return "unknown"

    def _flatten_bbox(self, bbox: Any) -> list[int]:
        if not isinstance(bbox, list):
            return []
        xs: list[int] = []
        ys: list[int] = []
        for point in bbox:
            if isinstance(point, list) and len(point) >= 2:
                xs.append(int(point[0]))
                ys.append(int(point[1]))
        if not xs or not ys:
            return []
        return [min(xs), min(ys), max(xs), max(ys)]
