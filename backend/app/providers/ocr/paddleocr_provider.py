from __future__ import annotations

import asyncio
import os
from pathlib import Path
from types import ModuleType
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
        try:
            raw_results = await asyncio.to_thread(engine.predict, str(image_path))
        except Exception as exc:
            raise self._wrap_runtime_error(exc) from exc
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
            # PaddlePaddle 3.3.x has a known CPU oneDNN regression on the OCR path.
            # Force the plain CPU path so Windows inference remains stable.
            os.environ.setdefault("FLAGS_enable_pir_api", "0")
            try:
                paddleocr_module = self._import_paddleocr_module()
            except ModuleNotFoundError as exc:
                if exc.name == "paddle":
                    raise RuntimeError(
                        "PaddleOCR requires the 'paddlepaddle' package. Install backend dependencies again or run "
                        "'python -m pip install paddlepaddle'."
                    ) from exc
                raise

            self._engine = paddleocr_module.PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                lang="korean",
                device="cpu",
                enable_mkldnn=False,
            )
        return self._engine

    def _import_paddleocr_module(self) -> ModuleType:
        import paddleocr

        return paddleocr

    def _wrap_runtime_error(self, exc: Exception) -> RuntimeError:
        message = str(exc)
        if "ConvertPirAttribute2RuntimeAttribute" in message or "onednn_instruction.cc" in message:
            return RuntimeError(
                "PaddleOCR failed on the PaddlePaddle CPU oneDNN runtime path. "
                "The backend already forces device='cpu' and enable_mkldnn=False for stability. "
                "If this still fails in your environment, pin PaddlePaddle to 3.2.2 and retry."
            )
        return RuntimeError(f"PaddleOCR inference failed: {message}")

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
