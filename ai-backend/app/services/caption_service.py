from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from app.core.config import Settings
from app.models.domain import CaptionBatchOutput, PanelReference, PanelUnderstanding, ScriptContext
from app.models.jobs import JobLogger
from app.utils.json_retry import parse_with_single_repair


class CaptionService:
    def __init__(self, settings: Settings, vision_provider, text_provider) -> None:
        self.settings = settings
        self.vision_provider = vision_provider
        self.text_provider = text_provider

    async def generate_understandings(
        self,
        *,
        context: ScriptContext,
        panels: list[PanelReference],
        file_paths: list[Path],
        on_log: JobLogger,
        check_cancel,
    ) -> tuple[list[PanelUnderstanding], str, int]:
        started_at = perf_counter()
        items: list[PanelUnderstanding] = []
        raw_parts: list[str] = []
        chunk_size = max(1, self.settings.caption_chunk_size)

        for start in range(0, len(panels), chunk_size):
            check_cancel()
            chunk_panels = panels[start : start + chunk_size]
            chunk_files = file_paths[start : start + chunk_size]
            prompt = self._build_prompt(context, chunk_panels)
            schema = CaptionBatchOutput.model_json_schema()
            on_log(
                "request",
                f"Caption batch {start // chunk_size + 1} with {len(chunk_panels)} panels",
                json.dumps({"panelIds": [panel.panelId for panel in chunk_panels]}, ensure_ascii=False, indent=2),
            )

            parsed, raw_output = await parse_with_single_repair(
                lambda: self.vision_provider.generate_structured(
                    prompt,
                    image_paths=chunk_files,
                    schema=schema,
                    system="Return JSON only.",
                    max_tokens=1024,
                ),
                lambda invalid_output: self.text_provider.repair_json(invalid_output=invalid_output, schema=schema),
                CaptionBatchOutput,
            )
            raw_parts.append(raw_output)
            for index, panel in enumerate(chunk_panels):
                draft = parsed.items[index] if index < len(parsed.items) else None
                items.append(
                    PanelUnderstanding(
                        panelId=panel.panelId,
                        orderIndex=panel.orderIndex,
                        summary=(draft.summary if draft else "") or f"Panel {panel.orderIndex + 1} summary unavailable",
                        action=(draft.action if draft else "") or "",
                        emotion=(draft.emotion if draft else "") or "",
                        dialogue=(draft.dialogue if draft else "") or "",
                        sfx=(draft.sfx if draft else []) or [],
                        cliffhanger=(draft.cliffhanger if draft else "") or "",
                    )
                )
            on_log("result", f"Structured caption ready for {len(chunk_panels)} panels")

        elapsed_ms = int((perf_counter() - started_at) * 1000)
        return items, "\n\n---\n\n".join(raw_parts), elapsed_ms

    def _build_prompt(self, context: ScriptContext, panels: list[PanelReference]) -> str:
        first_panel = panels[0].orderIndex + 1
        return f"""
You are a structured manga panel analyzer.
Analyze the uploaded manga panels in order and return compact JSON for each image.

Series context:
- Manga name: {context.mangaName}
- Main character: {context.mainCharacter}
- Story summary: {context.summary or "N/A"}
- Language: {context.language}

Panels in this batch:
- Start panel index: {first_panel}
- Number of panels: {len(panels)}

Rules:
- Return exactly one item per image in the same order.
- Keep summary between 8 and 16 words.
- Keep action and emotion short.
- Dialogue should be a short spoken-content summary or empty string.
- sfx must be a short array of tags.
- cliffhanger should pull into the next panel.
""".strip()
