from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from time import perf_counter
import asyncio

import httpx

from app.core.config import Settings
from app.models.api import ScriptJobOptions, ScriptJobResult
from app.models.domain import Metrics, PanelReference, PanelUnderstanding, RawOutputs, ScriptContext, ScriptItem, StoryMemory
from app.models.jobs import JobLogger
from app.utils.image_io import image_to_base64

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MAX_OUTPUT_TOKENS = 65536
RETRYABLE_STATUS_CODES = {429, 500, 503}


class GeminiScriptService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_script(
        self,
        *,
        context: ScriptContext,
        panels: list[PanelReference],
        file_paths: list[Path],
        options: ScriptJobOptions | None = None,
        on_log: JobLogger | None = None,
    ) -> ScriptJobResult:
        if len(panels) != len(file_paths):
            raise ValueError("Panel metadata count must match uploaded files.")

        api_key = self.settings.effective_gemini_api_key
        if not api_key:
            raise RuntimeError(
                "Gemini API key is not configured on the backend. Set AI_BACKEND_GEMINI_API_KEY or provide VITE_GEMINI_API_KEY in web-app/.env."
            )

        request_options = options or ScriptJobOptions()
        total_started = perf_counter()
        understanding_started = perf_counter()
        understandings, understanding_raw = await self._generate_understandings(
            api_key=api_key,
            context=context,
            panels=panels,
            file_paths=file_paths,
            on_log=on_log,
        )
        caption_ms = int((perf_counter() - understanding_started) * 1000)

        narration_started = perf_counter()
        generated_items, story_memories, script_raw = await self._generate_narration(
            api_key=api_key,
            context=context,
            understandings=understandings,
            on_log=on_log,
        )
        script_ms = int((perf_counter() - narration_started) * 1000)
        total_ms = int((perf_counter() - total_started) * 1000)

        panel_signature = json.dumps(
            [{"panelId": panel.panelId, "orderIndex": panel.orderIndex} for panel in panels],
            ensure_ascii=False,
        )

        return ScriptJobResult(
            understandings=understandings,
            generatedItems=generated_items,
            storyMemories=story_memories,
            panelSignature=panel_signature,
            rawOutputs=RawOutputs(
                understanding=understanding_raw if request_options.returnRawOutputs else "",
                script=script_raw if request_options.returnRawOutputs else "",
            )
            if request_options.returnRawOutputs
            else None,
            metrics=Metrics(
                panelCount=len(panels),
                totalMs=total_ms,
                captionMs=caption_ms,
                ocrMs=0,
                mergeMs=0,
                scriptMs=script_ms,
                avgPanelMs=round(total_ms / len(panels), 2) if panels else 0.0,
                captionSource="gemini_backend",
            ),
        )

    async def _generate_understandings(
        self,
        *,
        api_key: str,
        context: ScriptContext,
        panels: list[PanelReference],
        file_paths: list[Path],
        on_log: JobLogger | None,
    ) -> tuple[list[PanelUnderstanding], str]:
        batch_size = 20
        total_batches = (len(file_paths) + batch_size - 1) // batch_size
        items: list[PanelUnderstanding] = []
        raw_outputs: list[str] = []

        for batch_index in range(total_batches):
            start = batch_index * batch_size
            end = min(start + batch_size, len(file_paths))
            batch_paths = file_paths[start:end]
            batch_panels = panels[start:end]
            start_index = start + 1
            prompt = self._build_understanding_prompt(context, len(batch_paths), start_index)
            inline_data = [self._image_part(path) for path in batch_paths]

            self._log(
                on_log,
                "request",
                f"Stage 1/2 - Panel understanding batch {batch_index + 1}/{total_batches}",
                json.dumps(
                    {
                        "panels": [panel.panelId for panel in batch_panels],
                        "promptLength": len(prompt),
                        "imageCount": len(batch_paths),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            raw_text = await self._call_gemini(api_key=api_key, prompt=prompt, inline_data=inline_data)
            raw_outputs.append(raw_text)
            parsed = self._assert_batch_length(
                self._parse_json_array(raw_text, "panel understanding"),
                len(batch_paths),
                "panel understanding",
            )

            for index, item in enumerate(parsed):
                panel_ref = batch_panels[index]
                items.append(
                    PanelUnderstanding(
                        panelId=panel_ref.panelId,
                        orderIndex=panel_ref.orderIndex,
                        summary=str(item.get("summary", "")),
                        action=str(item.get("action", "")),
                        emotion=str(item.get("emotion", "")),
                        dialogue=str(item.get("dialogue", "")),
                        sfx=self._coerce_string_list(item.get("sfx")),
                        cliffhanger=str(item.get("cliffhanger", "")),
                    )
                )

            self._log(
                on_log,
                "result",
                f"Stage 1/2 complete for batch {batch_index + 1}/{total_batches}",
                json.dumps(parsed, ensure_ascii=False, indent=2),
            )

        return items, "\n\n---\n\n".join(raw_outputs)

    async def _generate_narration(
        self,
        *,
        api_key: str,
        context: ScriptContext,
        understandings: list[PanelUnderstanding],
        on_log: JobLogger | None,
    ) -> tuple[list[ScriptItem], list[StoryMemory], str]:
        batch_size = 20
        total_batches = (len(understandings) + batch_size - 1) // batch_size
        all_results: list[ScriptItem] = []
        story_memories: list[StoryMemory] = []
        raw_outputs: list[str] = []
        previous_context: str | None = None

        for batch_index in range(total_batches):
            start = batch_index * batch_size
            end = min(start + batch_size, len(understandings))
            batch_items = understandings[start:end]
            start_index = start + 1
            prompt = self._build_narration_prompt(context, batch_items, start_index, previous_context)

            self._log(
                on_log,
                "request",
                f"Stage 2/2 - Narration batch {batch_index + 1}/{total_batches}",
                json.dumps(
                    {
                        "panelRange": [start_index, end],
                        "promptLength": len(prompt),
                        "continuityApplied": bool(previous_context),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            raw_text = await self._call_gemini(api_key=api_key, prompt=prompt, inline_data=None)
            raw_outputs.append(raw_text)
            parsed = self._assert_batch_length(
                self._parse_json_array(raw_text, "script narration"),
                len(batch_items),
                "script narration",
            )

            chunk_results: list[ScriptItem] = []
            for index, item in enumerate(parsed):
                chunk_results.append(
                    ScriptItem(
                        panel_index=start_index + index,
                        ai_view=str(item.get("ai_view", "")),
                        voiceover_text=str(item.get("voiceover_text", "")),
                        sfx=self._coerce_string_list(item.get("sfx")),
                    )
                )

            all_results.extend(chunk_results)
            previous_context = self._build_narration_context_summary(chunk_results, context)
            story_memories.append(StoryMemory(chunkIndex=batch_index, summary=previous_context))

            self._log(
                on_log,
                "result",
                f"Stage 2/2 complete for batch {batch_index + 1}/{total_batches}",
                json.dumps([item.model_dump() for item in chunk_results], ensure_ascii=False, indent=2),
            )

        return all_results, story_memories, "\n\n---\n\n".join(raw_outputs)

    async def _call_gemini(
        self,
        *,
        api_key: str,
        prompt: str,
        inline_data: list[dict] | None,
    ) -> str:
        url = f"{GEMINI_API_BASE}/{self.settings.gemini_model}:generateContent?key={api_key}"
        body = {
            "contents": [
                {
                    "parts": [{"text": prompt}, *(inline_data or [])],
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
                "responseMimeType": "application/json",
            },
        }

        max_retries = 3
        attempt = 0
        last_error: Exception | None = None

        while attempt <= max_retries:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(url, json=body)
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    attempt += 1
                    continue
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    attempt += 1
                    continue
                raise RuntimeError(
                    f"Gemini API returned HTTP {exc.response.status_code} for model {self.settings.gemini_model}."
                ) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    attempt += 1
                    continue
                raise RuntimeError(
                    f"Gemini network error after retries for model {self.settings.gemini_model}: {type(exc).__name__}."
                ) from exc
        else:
            raise RuntimeError(
                f"Gemini request failed after retries for model {self.settings.gemini_model}: {type(last_error).__name__ if last_error else 'UnknownError'}."
            )

        text_content = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text")
        if not text_content:
            raise RuntimeError("Gemini returned an empty response.")
        return str(text_content)

    def _image_part(self, path: Path) -> dict:
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        return {
            "inlineData": {
                "mimeType": mime_type,
                "data": image_to_base64(
                    path,
                    max_width=self.settings.vision_max_width,
                    max_height=self.settings.vision_max_height,
                ),
            }
        }

    def _build_understanding_prompt(self, context: ScriptContext, panel_count: int, start_index: int) -> str:
        output_language = "English" if context.language == "en" else "Vietnamese"
        return f"""
You are a visual analyst for a manga recap workflow.
Analyze {panel_count} panels in top-to-bottom order and return one JSON array item per panel.

Series context:
- Title: {context.mangaName}
- Main character: {context.mainCharacter}
- Story summary: {context.summary or "N/A"}
- Output language: {output_language}

Return this schema:
[
  {{
    "panel_index": {start_index},
    "summary": "Short panel summary.",
    "action": "Short description of the main action.",
    "emotion": "1-3 words describing the mood.",
    "dialogue": "Very short summary of the important readable text, or empty string.",
    "sfx": ["sound", "effect"],
    "cliffhanger": "Short hook for what comes next."
  }}
]

Rules:
- Return JSON only.
- Return exactly {panel_count} items.
- panel_index must start at {start_index} and increase by 1.
- Keep every field concise and grounded in what is visible.
- Do not add fields outside the schema.
- Write all natural-language values in {output_language}.
""".strip()

    def _build_narration_prompt(
        self,
        context: ScriptContext,
        items: list[PanelUnderstanding],
        start_index: int,
        previous_script_context: str | None,
    ) -> str:
        output_language = "English" if context.language == "en" else "Vietnamese"
        context_block = (
            f"""
Previous chunk continuity:
---
{previous_script_context}
---
Keep continuity stable unless the current panels clearly contradict it.
""".strip()
            if previous_script_context
            else ""
        )

        understanding_lines: list[str] = []
        for index, item in enumerate(items):
            panel_index = start_index + index
            compact_fields = [
                f"summary: {item.summary}" if item.summary else "",
                f"action: {item.action}" if item.action else "",
                f"emotion: {item.emotion}" if item.emotion else "",
                f"dialogue: {item.dialogue}" if item.dialogue else "",
                f"sfx: {', '.join(item.sfx)}" if item.sfx else "",
                f"hook: {item.cliffhanger}" if item.cliffhanger else "",
            ]
            understanding_lines.append(f"[Panel {panel_index}] {' | '.join([field for field in compact_fields if field])}")

        return f"""
You are writing a high-tension YouTube manga recap script.
Do not re-interpret the images. Use only the structured panel understanding below.

Series context:
- Title: {context.mangaName}
- Main character: {context.mainCharacter}
- Story summary: {context.summary or "N/A"}
- Output language: {output_language}
{context_block}

Structured panel understanding:
---
{chr(10).join(understanding_lines)}
---

Return this schema:
[
  {{
    "panel_index": {start_index},
    "ai_view": "Short physical scene description.",
    "voiceover_text": "Natural recap narration for this panel.",
    "sfx": ["sound", "effect"]
  }}
]

Rules:
- Return JSON only.
- Return exactly {len(items)} items.
- panel_index must start at {start_index} and increase by 1.
- voiceover_text should be tight, engaging, and easy to read aloud.
- ai_view should describe the visible physical scene, not hidden plot facts.
- Reuse dialogue and sfx from the structured input when relevant.
- Write all natural-language values in {output_language}.
""".strip()

    def _build_narration_context_summary(self, items: list[ScriptItem], context: ScriptContext) -> str:
        lines: list[str] = []
        for item in items:
            line = f"[Panel {item.panel_index}]"
            if item.ai_view:
                line += f" {item.ai_view}."
            if item.voiceover_text:
                line += f' Narration: "{item.voiceover_text}"'
            lines.append(line)
        return f'Series "{context.mangaName}", main character: {context.mainCharacter}.\nRecent narration:\n' + "\n".join(lines)

    def _parse_json_array(self, text: str, label: str) -> list[dict]:
        clean_text = text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            parsed = json.loads(clean_text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            try:
                if not clean_text.endswith("]"):
                    last_brace = clean_text.rfind("}")
                    if last_brace != -1:
                        parsed = json.loads(f"{clean_text[: last_brace + 1]}\n]")
                        if isinstance(parsed, list):
                            return parsed
            except json.JSONDecodeError:
                pass

        raise RuntimeError(f"[Parse Error] Failed to parse {label}.\n\n=== RAW OUTPUT ===\n{clean_text}")

    def _assert_batch_length(self, items: list[dict], expected_count: int, label: str) -> list[dict]:
        if len(items) != expected_count:
            raise RuntimeError(f"Expected {expected_count} {label} items but received {len(items)}.")
        return items

    def _coerce_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    def _log(self, on_log: JobLogger | None, log_type: str, message: str, details: str | None = None) -> None:
        if on_log is not None:
            on_log(log_type, message, details)
