from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from app.models.domain import OCRLine, OCRResult


class PaddleOCRProvider:
    def __init__(self, *, min_confidence: float, max_text_lines: int, prefer_sfx: bool) -> None:
        self.min_confidence = min_confidence
        self.max_text_lines = max_text_lines
        self.prefer_sfx = prefer_sfx
        self._engine = None

    async def extract(self, image_path: Path, panel_id: str) -> OCRResult:
        engine = await asyncio.to_thread(self._get_engine)
        raw_results = await asyncio.to_thread(engine.predict, str(image_path))
        lines = self._normalize_lines(raw_results)
        return OCRResult(
            panel_id=panel_id,
            lines=lines,
            full_text=" ".join(line.text for line in lines).strip(),
            has_text=bool(lines),
        )

    def _get_engine(self):
        if self._engine is None:
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                lang="korean",
            )
        return self._engine

    def _normalize_lines(self, raw_results: list[Any]) -> list[OCRLine]:
        lines: list[OCRLine] = []
        for result in raw_results or []:
            payload = result if isinstance(result, dict) else getattr(result, "res", None)
            if not isinstance(payload, dict):
                continue
            polys = payload.get("dt_polys") or []
            texts = payload.get("rec_texts") or []
            scores = payload.get("rec_scores") or []
            for index, text in enumerate(texts):
                normalized_text = str(text).strip()
                confidence = float(scores[index] if index < len(scores) else 0.0)
                if not normalized_text or confidence < self.min_confidence:
                    continue
                bbox = polys[index] if index < len(polys) else []
                lines.append(
                    OCRLine(
                        text=normalized_text,
                        confidence=confidence,
                        role=self._classify_role(normalized_text),
                        bbox=self._flatten_bbox(bbox),
                    )
                )
        return lines[: self.max_text_lines]

    def _classify_role(self, text: str) -> str:
        normalized = text.strip()
        compact = normalized.replace(" ", "")
        if self.prefer_sfx and (
            len(compact) <= 6
            or any(char in compact for char in ("!", "?", "~", "…"))
            or sum(char.isalpha() for char in compact) <= 2
        ):
            return "sfx"
        if " " in normalized or any(char in normalized for char in (".", ",", ":", ";", "\"", "'")):
            return "dialogue"
        return "unknown"

    def _flatten_bbox(self, bbox: Any) -> list[int]:
        xs: list[int] = []
        ys: list[int] = []
        for point in bbox if isinstance(bbox, list) else []:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                xs.append(int(point[0]))
                ys.append(int(point[1]))
        if not xs or not ys:
            return []
        return [min(xs), min(ys), max(xs), max(ys)]
