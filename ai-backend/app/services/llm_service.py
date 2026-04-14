from __future__ import annotations

import json
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
            parsed, raw_output = await parse_with_single_repair(
                lambda: self.text_provider.generate_text(prompt, schema=script_schema, max_tokens=1400),
                lambda invalid_output: self.text_provider.repair_json(invalid_output=invalid_output, schema=script_schema),
                ScriptChunkOutput,
            )
            raw_parts.append(raw_output)
            chunk_items: list[ScriptItem] = []
            for index, understanding in enumerate(chunk):
                draft = parsed.items[index] if index < len(parsed.items) else None
                chunk_items.append(
                    ScriptItem(
                        panel_index=understanding.orderIndex + 1,
                        ai_view=(draft.ai_view if draft else "") or understanding.summary,
                        voiceover_text=(draft.voiceover_text if draft else "") or "Narration unavailable.",
                        sfx=(draft.sfx if draft else []) or understanding.sfx,
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
                        f"action: {item.action or 'N/A'}",
                        f"emotion: {item.emotion or 'N/A'}",
                        f"dialogue: {item.dialogue or 'N/A'}",
                        f"sfx: {', '.join(item.sfx) or 'none'}",
                        f"hook: {item.cliffhanger or 'N/A'}",
                    ]
                )
                for item in chunk
            ]
        )
        previous_summary = previous_memory.summary if previous_memory else "none"
        return f"""
You are writing recap narration for manga panels.
Write one narration item per panel and keep continuity tight.

Series context:
- Manga name: {context.mangaName}
- Main character: {context.mainCharacter}
- Story summary: {context.summary or "N/A"}
- Language: {context.language}
- Current chunk: {chunk_index + 1}
- Previous story memory: {previous_summary}

Structured panel input:
{input_block}

Rules:
- Return exactly one item per panel in the same order.
- voiceover_text should be concise, energetic, and TTS-friendly.
- ai_view should describe the physical scene.
- Reuse only the given structured inputs and previous story memory.
""".strip()

    def _build_memory_prompt(self, context: ScriptContext, items: list[ScriptItem]) -> str:
        script_block = "\n".join([f"[Panel {item.panel_index}] {item.voiceover_text}" for item in items])
        return f"""
Summarize this manga recap chunk into 1-2 short sentences for future context.

Series context:
- Manga name: {context.mangaName}
- Main character: {context.mainCharacter}

Chunk narration:
{script_block}
""".strip()
