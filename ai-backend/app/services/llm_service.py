from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from time import perf_counter

from app.core.config import Settings
from app.models.domain import (
    PanelUnderstanding,
    ScriptChunkOutput,
    ScriptContext,
    ScriptItem,
    StoryMemory,
    StoryMemoryOutput,
)
from app.models.jobs import JobLogger
from app.utils.json_retry import parse_with_single_repair

NOTE_SCRIPT_TEMPLATE = ""
try:
    NOTE_SCRIPT_TEMPLATE = (Path(__file__).resolve().parents[3] / "note_script.txt").read_text(encoding="utf-8").strip()
except OSError:
    NOTE_SCRIPT_TEMPLATE = ""

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, settings: Settings, text_provider) -> None:
        self.settings = settings
        self.text_provider = text_provider

    async def generate_script(
        self,
        *,
        context: ScriptContext,
        understandings: list[PanelUnderstanding],
        on_log: JobLogger,
        check_cancel,
    ) -> tuple[list[ScriptItem], list[StoryMemory], str, int]:
        started_at = perf_counter()
        items: list[ScriptItem] = []
        memories: list[StoryMemory] = []
        raw_parts: list[str] = []
        previous_memory: StoryMemory | None = None
        chunk_size = max(1, self.settings.script_chunk_size)

        for start in range(0, len(understandings), chunk_size):
            check_cancel()
            chunk = understandings[start : start + chunk_size]
            chunk_index = start // chunk_size
            script_schema = ScriptChunkOutput.model_json_schema()
            prompt = self._build_script_prompt(context, chunk, chunk_index, previous_memory)
            on_log(
                "request",
                f"Script batch {chunk_index + 1} with {len(chunk)} panels",
                json.dumps({"panelIds": [item.panelId for item in chunk]}, ensure_ascii=False, indent=2),
            )
            parsed, raw_output = await self._generate_script_chunk_with_retry(
                context=context,
                chunk=chunk,
                chunk_index=chunk_index,
                prompt=prompt,
                schema=script_schema,
                on_log=on_log,
                check_cancel=check_cancel,
            )
            raw_parts.append(raw_output)
            chunk_items: list[ScriptItem] = []
            for index, understanding in enumerate(chunk):
                draft = parsed.items[index]
                chunk_items.append(
                    ScriptItem(
                        panel_index=understanding.orderIndex + 1,
                        voiceover_text=draft.voiceover_text.strip(),
                    )
                )
            items.extend(chunk_items)
            on_log("result", f"Generated narration for batch {chunk_index + 1}")

            memory_schema = StoryMemoryOutput.model_json_schema()
            memory_prompt = self._build_memory_prompt(context, chunk_items)
            memory_parsed, memory_raw_output = await parse_with_single_repair(
                lambda: self.text_provider.generate_text(memory_prompt, schema=memory_schema, max_tokens=300),
                lambda invalid_output: self.text_provider.repair_json(invalid_output=invalid_output, schema=memory_schema),
                StoryMemoryOutput,
            )
            previous_memory = StoryMemory(
                chunkIndex=chunk_index,
                summary=memory_parsed.summary.strip() or f"Chunk {chunk_index + 1} memory unavailable.",
            )
            memories.append(previous_memory)
            raw_parts.append(memory_raw_output)
            on_log("result", f"Generated memory for batch {chunk_index + 1}", previous_memory.summary)

        elapsed_ms = int((perf_counter() - started_at) * 1000)
        return items, memories, "\n\n---\n\n".join(raw_parts), elapsed_ms

    async def _generate_script_chunk_with_retry(
        self,
        *,
        context: ScriptContext,
        chunk: list[PanelUnderstanding],
        chunk_index: int,
        prompt: str,
        schema: dict,
        on_log: JobLogger,
        check_cancel,
    ) -> tuple[ScriptChunkOutput, str]:
        max_attempts = max(1, self.settings.script_generation_retries + 1)
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            check_cancel()
            try:
                parsed, raw_output = await parse_with_single_repair(
                    lambda: self.text_provider.generate_text(prompt, schema=schema, max_tokens=1400),
                    lambda invalid_output: self.text_provider.repair_json(invalid_output=invalid_output, schema=schema),
                    ScriptChunkOutput,
                )
                self._validate_script_chunk_output(context, chunk, parsed, raw_output)
                return parsed, raw_output
            except Exception as exc:
                last_error = exc
                details = json.dumps(
                    {
                        "stage": "script",
                        "errorCategory": "script chunk validation failed",
                        "chunkIndex": chunk_index + 1,
                        "attempt": attempt,
                        "maxAttempts": max_attempts,
                        "panelIds": [item.panelId for item in chunk],
                        "model": self.settings.text_model,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                logger.warning(
                    "script chunk generation failed | chunk=%s attempt=%s/%s model=%s error=%s",
                    chunk_index + 1,
                    attempt,
                    max_attempts,
                    self.settings.text_model,
                    exc,
                )
                on_log("error", "script chunk validation failed", details)
                if attempt >= max_attempts:
                    break
                await asyncio.sleep(self.settings.script_retry_delay_seconds)

        raise RuntimeError("script chunk validation failed") from last_error

    def _validate_script_chunk_output(
        self,
        context: ScriptContext,
        chunk: list[PanelUnderstanding],
        parsed: ScriptChunkOutput,
        raw_output: str,
    ) -> None:
        expected_count = len(chunk)
        actual_count = len(parsed.items)
        if actual_count != expected_count:
            raise ValueError(
                f"Expected {expected_count} script items but received {actual_count}. Raw output: {raw_output}"
            )

        expected_panel_indexes = [item.orderIndex + 1 for item in chunk]
        actual_panel_indexes = [item.panel_index for item in parsed.items]
        if actual_panel_indexes != expected_panel_indexes:
            raise ValueError(
                f"Expected panel indexes {expected_panel_indexes} but received {actual_panel_indexes}. Raw output: {raw_output}"
            )

        if context.language == "vi":
            english_markers = ("suddenly", "meanwhile", "however", "then", "dark shadow")
            for item in parsed.items:
                text = item.voiceover_text.lower()
                if any(marker in text for marker in english_markers):
                    raise ValueError(f"Detected English phrasing in Vietnamese output. Raw output: {raw_output}")

        for item in parsed.items:
            if not item.voiceover_text.strip():
                raise ValueError(f"Empty voiceover_text detected. Raw output: {raw_output}")

    def _build_script_prompt(
        self,
        context: ScriptContext,
        chunk: list[PanelUnderstanding],
        chunk_index: int,
        previous_memory: StoryMemory | None,
    ) -> str:
        input_block = "\n".join(
            [
                " | ".join(
                    [
                        f"[Panel {item.orderIndex + 1}]",
                        f"summary: {item.summary or 'N/A'}",
                        f"main_event: {item.main_event or 'N/A'}",
                        f"inset_event: {item.inset_event or 'N/A'}",
                        f"visible_objects: {', '.join(item.visible_objects) or 'none'}",
                        f"visible_text: {', '.join(item.visible_text) or 'none'}",
                        f"scene_tone: {item.scene_tone or 'N/A'}",
                        f"action: {item.action or 'N/A'}",
                        f"emotion: {item.emotion or 'N/A'}",
                        f"dialogue: {item.dialogue or 'N/A'}",
                        f"hook: {item.narrative_hook or item.cliffhanger or 'N/A'}",
                    ]
                )
                for item in chunk
            ]
        )
        previous_summary = previous_memory.summary if previous_memory else "none"
        language_label = "Vietnamese" if context.language == "vi" else "English"
        note_block = (
            f"""
Internal script note to follow:
---
{NOTE_SCRIPT_TEMPLATE}
---
"""
            if NOTE_SCRIPT_TEMPLATE
            else ""
        )
        continuity_block = (
            f"""
This is the continuation of the chapter. Keep the narrative flow consistent with the previous chunk summary below:
---
{previous_summary}
---
Keep naming, tone, and continuity stable unless the current structured inputs clearly contradict it.
"""
            if previous_memory
            else ""
        )
        return f"""
You are a YouTube manga recap writer working in a high-tension recap style.
You do not need to infer the image again. You must write narration only from the structured panel understanding below.

Series context:
- Manga name: {context.mangaName}
- Main character: {context.mainCharacter}
- Story summary: {context.summary or "N/A"}
- Output language: {language_label}
- Current chunk: {chunk_index + 1}
{note_block}
{continuity_block}

Structured panel input:
{input_block}

Rules:
- Return exactly one item per panel in the same order.
- You must return exactly {len(chunk)} items.
- The panel_index values must be exactly: {", ".join(str(item.orderIndex + 1) for item in chunk)}.
- voiceover_text must feel fast, engaging, tense, and natural for one narrator reading aloud.
- Keep sentences concise and TTS-friendly.
- If dialogue appears in the structured input, blend it naturally into the narration. Do not present it like a dry report.
- Use only the provided structured inputs and previous story memory. Do not invent plot facts.
- Prefer main_event, inset_event, visible_objects, visible_text, and scene_tone over dramatic interpretation.
- Do not force the main character's name into every panel.
- Only mention {context.mainCharacter} when the structured input clearly supports that this panel is actually about that character.
- If the acting character is unclear, describe the person generically instead of assigning the main character's name.
- All natural-language field values must be written in {language_label}.
- If Output language is Vietnamese, do not use English words or English connective phrases.
- Every item must include voiceover_text.
- Return JSON only.
""".strip()

    def _build_memory_prompt(self, context: ScriptContext, items: list[ScriptItem]) -> str:
        script_block = "\n".join([f"[Panel {item.panel_index}] {item.voiceover_text}" for item in items])
        language_label = "Vietnamese" if context.language == "vi" else "English"
        return f"""
Summarize this manga recap chunk into 1-2 short sentences for future context.

Series context:
- Manga name: {context.mangaName}
- Main character: {context.mainCharacter}
- Output language: {language_label}

Chunk narration:
{script_block}

Rules:
- Keep the memory concise.
- Preserve only the information needed for continuity in the next chunk.
- Write the summary in {language_label}.
""".strip()
