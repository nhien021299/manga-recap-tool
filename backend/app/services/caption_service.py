from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from app.core.config import Settings
from app.models.domain import (
    MergeDiagnostics,
    OCRResult,
    PanelReference,
    PanelUnderstanding,
    ScriptContext,
    VisionCaptionBatchOutput,
    VisionCaptionRaw,
)
from app.models.jobs import JobLogger
from app.utils.json_retry import (
    JsonRepairFailedError,
    RawProviderError,
    RepairedJsonValidationFailedError,
    parse_with_single_repair,
)

logger = logging.getLogger(__name__)

VI_INSET_PREFIX = "Khung phá»¥: "
EN_INSET_PREFIX = "Inset: "
VI_GENERIC_FIGURE = "hÃ¬nh thá»ƒ mÆ¡ há»“"
EN_GENERIC_FIGURE = "unclear figure"
SUPERNATURAL_TERMS = (
    "ghost",
    "monster",
    "spirit",
    "demon",
    "apparition",
    "ma",
    "quá»·",
    "yÃªu quÃ¡i",
    "linh há»“n",
)


@dataclass
class CaptionPanelArtifacts:
    panel: PanelReference
    ocr: OCRResult
    vision: VisionCaptionRaw
    understanding: PanelUnderstanding
    diagnostics: MergeDiagnostics


@dataclass
class CaptionStageResult:
    understandings: list[PanelUnderstanding]
    raw_output: str
    caption_ms: int
    ocr_ms: int
    merge_ms: int
    avg_panel_ms: float
    caption_source: str
    panel_artifacts: list[CaptionPanelArtifacts]


class CaptionService:
    def __init__(self, settings: Settings, vision_provider, text_provider, ocr_provider=None) -> None:
        self.settings = settings
        self.vision_provider = vision_provider
        self.text_provider = text_provider
        self.ocr_provider = ocr_provider

    async def generate_understandings(
        self,
        *,
        context: ScriptContext,
        panels: list[PanelReference],
        file_paths: list[Path],
        on_log: JobLogger,
        check_cancel,
    ) -> CaptionStageResult:
        started_at = perf_counter()
        items: list[PanelUnderstanding] = []
        raw_parts: list[str] = []
        panel_artifacts: list[CaptionPanelArtifacts] = []
        chunk_size = max(1, self.settings.caption_chunk_size)
        total_ocr_ms = 0
        total_merge_ms = 0
        caption_source = "vision_ocr" if self.ocr_provider is not None else "vision_only"
        debug_run_dir = self._prepare_debug_dir() if self.settings.ocr_debug_save_json else None

        for start in range(0, len(panels), chunk_size):
            check_cancel()
            chunk_panels = panels[start : start + chunk_size]
            chunk_files = file_paths[start : start + chunk_size]
            ocr_results, ocr_elapsed_ms = await self._extract_ocr(
                chunk_panels=chunk_panels,
                chunk_files=chunk_files,
                on_log=on_log,
                check_cancel=check_cancel,
            )
            total_ocr_ms += ocr_elapsed_ms

            prompt = self._build_prompt(context, chunk_panels)
            schema = self._build_caption_schema(len(chunk_panels))
            on_log(
                "request",
                f"Caption batch {start // chunk_size + 1} with {len(chunk_panels)} panels",
                json.dumps(
                    {
                        "panelIds": [panel.panelId for panel in chunk_panels],
                        "captionSource": caption_source,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            try:
                parsed, raw_output = await parse_with_single_repair(
                    lambda: self.vision_provider.generate_structured(
                        prompt,
                        image_paths=chunk_files,
                        schema=schema,
                        system="Return JSON only.",
                        max_tokens=self.settings.caption_max_tokens,
                    ),
                    lambda invalid_output: self.text_provider.repair_json(invalid_output=invalid_output, schema=schema),
                    VisionCaptionBatchOutput,
                )
            except RawProviderError as exc:
                details = json.dumps(
                    {
                        "stage": "caption",
                        "errorCategory": "caption raw provider error",
                        "batchIndex": start // chunk_size + 1,
                        "panelIds": [panel.panelId for panel in chunk_panels],
                        "provider": "ollama_vision",
                        "model": self.settings.vision_model,
                        "baseUrl": self.settings.vision_base_url,
                        "timeoutSeconds": self.settings.vision_timeout_seconds,
                        "timeoutRetries": self.settings.vision_timeout_retries,
                        "retryDelaySeconds": self.settings.vision_retry_delay_seconds,
                        "visionMaxWidth": self.settings.vision_max_width,
                        "visionMaxHeight": self.settings.vision_max_height,
                        "captionMaxTokens": self.settings.caption_max_tokens,
                        "captionSource": caption_source,
                        "exception": str(exc),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                logger.exception("caption raw provider error | batch=%s model=%s", start // chunk_size + 1, self.settings.vision_model)
                on_log("error", "caption raw provider error", details)
                raise RuntimeError("caption raw provider error") from exc
            except RepairedJsonValidationFailedError as exc:
                details = json.dumps(
                    {
                        "stage": "caption",
                        "errorCategory": "caption JSON validation failed",
                        "batchIndex": start // chunk_size + 1,
                        "panelIds": [panel.panelId for panel in chunk_panels],
                        "provider": "ollama_vision",
                        "model": self.settings.vision_model,
                        "baseUrl": self.settings.vision_base_url,
                        "validationError": str(exc.validation_error),
                        "rawOutput": exc.raw_output,
                        "repairedOutput": exc.repaired_output,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                logger.exception(
                    "caption JSON validation failed | batch=%s model=%s",
                    start // chunk_size + 1,
                    self.settings.vision_model,
                )
                on_log("error", "caption JSON validation failed", details)
                raise RuntimeError("caption JSON validation failed") from exc
            except JsonRepairFailedError as exc:
                details = json.dumps(
                    {
                        "stage": "caption",
                        "errorCategory": "caption repair failed",
                        "batchIndex": start // chunk_size + 1,
                        "panelIds": [panel.panelId for panel in chunk_panels],
                        "repairProvider": self.settings.text_provider,
                        "repairModel": self.settings.text_model,
                        "repairBaseUrl": self.settings.text_base_url,
                        "repairError": str(exc.cause),
                        "rawOutput": exc.raw_output,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                logger.exception(
                    "caption repair failed | batch=%s repair_model=%s",
                    start // chunk_size + 1,
                    self.settings.text_model,
                )
                on_log("error", "caption repair failed", details)
                raise RuntimeError("caption repair failed") from exc

            if len(parsed.items) != len(chunk_panels):
                details = json.dumps(
                    {
                        "stage": "caption",
                        "errorCategory": "caption item count mismatch",
                        "batchIndex": start // chunk_size + 1,
                        "expectedCount": len(chunk_panels),
                        "actualCount": len(parsed.items),
                        "panelIds": [panel.panelId for panel in chunk_panels],
                        "model": self.settings.vision_model,
                        "rawOutput": raw_output,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                logger.error(
                    "caption item count mismatch | batch=%s expected=%s actual=%s",
                    start // chunk_size + 1,
                    len(chunk_panels),
                    len(parsed.items),
                )
                on_log("error", "caption item count mismatch", details)
                raise RuntimeError("caption item count mismatch")

            raw_parts.append(raw_output)
            merge_started_at = perf_counter()
            for index, panel in enumerate(chunk_panels):
                vision_raw = self._normalize_vision_raw(panel, parsed.items[index])
                understanding, diagnostics = self._merge_panel(
                    context=context,
                    panel=panel,
                    vision=vision_raw,
                    ocr=ocr_results[index],
                    caption_source=caption_source,
                )
                items.append(understanding)
                artifact = CaptionPanelArtifacts(
                    panel=panel,
                    ocr=ocr_results[index],
                    vision=vision_raw,
                    understanding=understanding,
                    diagnostics=diagnostics,
                )
                panel_artifacts.append(artifact)
                if debug_run_dir is not None:
                    self._save_debug_panel(debug_run_dir, artifact)
            merge_elapsed_ms = int((perf_counter() - merge_started_at) * 1000)
            total_merge_ms += merge_elapsed_ms
            on_log("result", f"Structured caption ready for {len(chunk_panels)} panels")

        elapsed_ms = int((perf_counter() - started_at) * 1000)
        avg_panel_ms = round(elapsed_ms / len(panels), 2) if panels else 0.0
        return CaptionStageResult(
            understandings=items,
            raw_output="\n\n---\n\n".join(raw_parts),
            caption_ms=elapsed_ms,
            ocr_ms=total_ocr_ms,
            merge_ms=total_merge_ms,
            avg_panel_ms=avg_panel_ms,
            caption_source=caption_source,
            panel_artifacts=panel_artifacts,
        )

    async def _extract_ocr(
        self,
        *,
        chunk_panels: list[PanelReference],
        chunk_files: list[Path],
        on_log: JobLogger,
        check_cancel,
    ) -> tuple[list[OCRResult], int]:
        if self.ocr_provider is None:
            return [OCRResult(panel_id=panel.panelId) for panel in chunk_panels], 0

        started_at = perf_counter()
        results: list[OCRResult] = []
        for panel, file_path in zip(chunk_panels, chunk_files):
            check_cancel()
            result = await self.ocr_provider.extract(file_path, panel.panelId)
            results.append(result)

        elapsed_ms = int((perf_counter() - started_at) * 1000)
        on_log(
            "result",
            f"OCR extracted for {len(chunk_panels)} panels",
            json.dumps(
                {
                    "panelIds": [panel.panelId for panel in chunk_panels],
                    "ocrMs": elapsed_ms,
                    "ocrLineCount": sum(len(result.lines) for result in results),
                    "ocrHasText": any(result.has_text for result in results),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        return results, elapsed_ms

    def _normalize_vision_raw(self, panel: PanelReference, raw: VisionCaptionRaw) -> VisionCaptionRaw:
        return VisionCaptionRaw(
            panel_index=raw.panel_index or panel.orderIndex + 1,
            panel_id=panel.panelId,
            main_event=raw.main_event.strip(),
            inset_event=raw.inset_event.strip(),
            visible_objects=self._clean_list(raw.visible_objects),
            visible_text=self._clean_list(raw.visible_text),
            scene_tone=raw.scene_tone.strip(),
        )

    def _merge_panel(
        self,
        *,
        context: ScriptContext,
        panel: PanelReference,
        vision: VisionCaptionRaw,
        ocr: OCRResult,
        caption_source: str,
    ) -> tuple[PanelUnderstanding, MergeDiagnostics]:
        correction_tags: list[str] = []
        main_event = self._sanitize_text(vision.main_event, context.language, correction_tags)
        inset_event = self._sanitize_text(vision.inset_event, context.language, correction_tags)
        visible_objects = [self._sanitize_text(item, context.language, correction_tags) for item in vision.visible_objects]
        visible_objects = self._clean_list(visible_objects)
        visible_text = self._merge_visible_text(vision.visible_text, ocr)
        dialogue = self._build_dialogue(ocr, correction_tags)
        summary = self._build_summary(context.language, main_event, inset_event)
        action = self._build_action(context.language, main_event, inset_event)
        if inset_event:
            correction_tags.append("inset_recovered")

        if not summary:
            summary = f"Panel {panel.orderIndex + 1} summary unavailable"
        scene_tone = vision.scene_tone.strip()
        emotion = scene_tone or ("CÄƒng tháº³ng" if context.language == "vi" else "tense")
        narrative_hook = self._build_narrative_hook(context.language, action, dialogue)

        understanding = PanelUnderstanding(
            panelId=panel.panelId,
            orderIndex=panel.orderIndex,
            summary=summary,
            main_event=main_event,
            inset_event=inset_event,
            visible_objects=visible_objects,
            visible_text=visible_text,
            scene_tone=scene_tone,
            action=action or main_event,
            emotion=emotion,
            dialogue=dialogue,
            cliffhanger=narrative_hook,
            narrative_hook=narrative_hook,
        )
        diagnostics = MergeDiagnostics(
            correction_tags=self._clean_list(correction_tags),
            ocr_has_text=ocr.has_text,
            ocr_line_count=len(ocr.lines),
            caption_source=caption_source,
        )
        return understanding, diagnostics

    def _merge_visible_text(self, visible_text: list[str], ocr: OCRResult) -> list[str]:
        merged = list(visible_text)
        merged.extend(line.text for line in ocr.lines)
        return self._clean_list(merged)

    def _build_dialogue(self, ocr: OCRResult, correction_tags: list[str]) -> str:
        dialogue_lines = [line.text for line in ocr.lines if line.role == "dialogue"]
        if dialogue_lines:
            correction_tags.append("dialogue_grounded")
        return " ".join(dialogue_lines).strip()

    def _build_summary(self, language: str, main_event: str, inset_event: str) -> str:
        if not main_event and not inset_event:
            return ""
        if main_event and inset_event:
            prefix = VI_INSET_PREFIX if language == "vi" else EN_INSET_PREFIX
            return f"{main_event}. {prefix}{inset_event}"
        return main_event or inset_event

    def _build_action(self, language: str, main_event: str, inset_event: str) -> str:
        if main_event and inset_event:
            connector = " Äá»“ng thá»i, " if language == "vi" else " Meanwhile, "
            return f"{main_event}{connector}{inset_event}".strip()
        return main_event or inset_event

    def _build_narrative_hook(self, language: str, action: str, dialogue: str) -> str:
        if action:
            return action
        if dialogue:
            return dialogue
        return "Tension keeps rising." if language != "vi" else "Cang thang van tiep tuc dang len."

    def _sanitize_text(self, value: str, language: str, correction_tags: list[str]) -> str:
        sanitized = value.strip()
        lower = sanitized.lower()
        if any(term in lower for term in SUPERNATURAL_TERMS):
            replacement = VI_GENERIC_FIGURE if language == "vi" else EN_GENERIC_FIGURE
            for term in SUPERNATURAL_TERMS:
                sanitized = sanitized.replace(term, replacement)
                sanitized = sanitized.replace(term.title(), replacement)
            correction_tags.append("hallucination_dampened")
        return sanitized.strip()

    def _clean_list(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
        return cleaned

    def _prepare_debug_dir(self) -> Path:
        debug_dir = self.settings.ocr_debug_root / uuid.uuid4().hex
        debug_dir.mkdir(parents=True, exist_ok=True)
        return debug_dir

    def _build_caption_schema(self, expected_count: int) -> dict:
        schema = VisionCaptionBatchOutput.model_json_schema()
        items_schema = schema.get("properties", {}).get("items", {})
        if isinstance(items_schema, dict):
            items_schema["minItems"] = expected_count
            items_schema["maxItems"] = expected_count
            item_ref = items_schema.get("items", {}).get("$ref")
            if item_ref and item_ref.startswith("#/$defs/"):
                def_name = item_ref.split("/")[-1]
                item_def = schema.get("$defs", {}).get(def_name, {})
                properties = item_def.get("properties", {})
                properties.pop("panel_id", None)
                required = item_def.get("required", [])
                if "panel_id" in required:
                    item_def["required"] = [field for field in required if field != "panel_id"]
        return schema

    def _save_debug_panel(self, debug_dir: Path, artifact: CaptionPanelArtifacts) -> None:
        payload = {
            "panelId": artifact.panel.panelId,
            "ocr": artifact.ocr.model_dump(),
            "vision": artifact.vision.model_dump(),
            "understanding": artifact.understanding.model_dump(),
            "mergeDiagnostics": artifact.diagnostics.model_dump(),
        }
        (debug_dir / f"{artifact.panel.panelId}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_prompt(self, context: ScriptContext, panels: list[PanelReference]) -> str:
        first_panel = panels[0].orderIndex + 1
        language_label = "Vietnamese" if context.language == "vi" else "English"
        return f"""
You are a visual analyst for manga/manhwa recap.
Analyze the uploaded panels in top-to-bottom order and return structured JSON for each panel.

Output language: {language_label}

Panels in this batch:
- Start panel index: {first_panel}
- Number of panels: {len(panels)}

Rules:
- Return exactly one item per image in the same order.
- Return one top-level JSON object with an `items` array.
- Each item must include these keys: panel_index, main_event, inset_event, visible_objects, visible_text scene_tone.
- panel_index must match the panel order in this batch starting from {first_panel}.
- Describe only what is directly visible in each panel.
- Do not infer ghost, monster, identity, or story meaning unless it is clearly visible.
- If a panel includes both a main scene and an inset/sub-panel, separate them into main_event and inset_event.
- If no inset/sub-panel exists, return an empty string for inset_event.
- visible_objects should list only the most important visible objects or scene elements.
- visible_text should list readable or partly readable on-panel text exactly as seen.
- If text is stylized, partly obscured, or unreadable, keep it in visible_text as unreadable text.
- scene_tone should describe visual tension or atmosphere in 2 to 5 words.
- Keep every field short, concrete, and grounded.
- All natural-language field values must be written in {language_label}.
- Return JSON only.
""".strip()

