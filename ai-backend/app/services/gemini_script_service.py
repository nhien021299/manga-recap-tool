from __future__ import annotations

import asyncio
import json
import mimetypes
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import openai

from app.core.config import Settings
from app.models.api import ScriptJobOptions, ScriptJobResult
from app.models.domain import Metrics, PanelReference, RawOutputs, ScriptContext, ScriptItem, StoryMemory
from app.models.jobs import JobLogger, JobRecord
from app.services.gemini_request_gate import GeminiRequestGate
from app.utils.image_io import image_to_base64

MAX_OUTPUT_TOKENS = 8192
MAX_MEMORY_WORDS = 50
MAX_MEMORY_CHARS = 280
MAX_RECENT_NAMES = 3
MAX_HINT_NAMES = 2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class IdentityEvidence:
    candidate_pool: list[str]
    confirmed_names: list[str]
    carryover_names: list[str]
    has_text_signal: bool
    use_neutral_fallback: bool
    neutral_fallback_reason: str
    ocr_line_count: int = 0
    ocr_provider: str = "disabled"
    ocr_elapsed_ms: int = 0


@dataclass
class GenerationStats:
    prompt_tokens: int = 0
    candidates_tokens: int = 0
    total_tokens: int = 0
    retry_count: int = 0
    rate_limited_count: int = 0
    throttle_wait_ms: int = 0
    identity_ocr_ms: int = 0
    identity_confirmed_count: int = 0
    batch_size_used: int = 0


class GeminiScriptService:
    def __init__(
        self,
        settings: Settings,
        *,
        identity_ocr_provider: Any | None = None,
        gemini_request_gate: GeminiRequestGate | None = None,
    ) -> None:
        self.settings = settings
        self.identity_ocr_provider = identity_ocr_provider
        self.gemini_request_gate = gemini_request_gate

    async def run_job(self, job: JobRecord) -> ScriptJobResult:
        def on_log(log_type: str, message: str, details: str | None = None) -> None:
            job.add_log(log_type, message, details)

        return await self.generate_script(
            context=job.request.context,
            panels=job.request.panels,
            file_paths=job.file_paths,
            options=job.request.options,
            on_log=on_log,
        )

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
                "Gemini API key is not configured on the backend. Set AI_BACKEND_GEMINI_API_KEY in ai-backend/.env."
            )

        request_options = options or ScriptJobOptions()
        total_started = perf_counter()

        generated_items, story_memories, script_raw, stats = await self._generate_script_batches(
            api_key=api_key,
            context=context,
            panels=panels,
            file_paths=file_paths,
            on_log=on_log,
        )

        script_ms = int((perf_counter() - total_started) * 1000)
        panel_signature = json.dumps(
            [{"panelId": panel.panelId, "orderIndex": panel.orderIndex} for panel in panels],
            ensure_ascii=False,
        )

        return ScriptJobResult(
            understandings=[],
            generatedItems=generated_items,
            storyMemories=story_memories,
            panelSignature=panel_signature,
            rawOutputs=RawOutputs(
                understanding="",
                script=script_raw if request_options.returnRawOutputs else "",
            )
            if request_options.returnRawOutputs
            else None,
            metrics=Metrics(
                panelCount=len(panels),
                totalMs=script_ms,
                captionMs=0,
                ocrMs=0,
                mergeMs=0,
                scriptMs=script_ms,
                avgPanelMs=round(script_ms / len(panels), 2) if panels else 0.0,
                captionSource="gemini_unified_backend",
                totalPromptTokens=stats.prompt_tokens,
                totalCandidatesTokens=stats.candidates_tokens,
                totalTokens=stats.total_tokens,
                batchSizeUsed=stats.batch_size_used,
                retryCount=stats.retry_count,
                rateLimitedCount=stats.rate_limited_count,
                throttleWaitMs=stats.throttle_wait_ms,
                identityOcrMs=stats.identity_ocr_ms,
                identityConfirmedCount=stats.identity_confirmed_count,
            ),
        )

    async def _generate_script_batches(
        self,
        *,
        api_key: str,
        context: ScriptContext,
        panels: list[PanelReference],
        file_paths: list[Path],
        on_log: JobLogger | None,
    ) -> tuple[list[ScriptItem], list[StoryMemory], str, GenerationStats]:
        batch_size = max(1, self.settings.gemini_script_batch_size)
        total_batches = (len(file_paths) + batch_size - 1) // batch_size
        stats = GenerationStats(batch_size_used=batch_size)
        all_results: list[ScriptItem] = []
        story_memories: list[StoryMemory] = []
        raw_outputs: list[str] = []
        previous_memory: StoryMemory | None = None

        for batch_index in range(total_batches):
            start = batch_index * batch_size
            end = min(start + batch_size, len(file_paths))
            batch_paths = file_paths[start:end]
            batch_panels = panels[start:end]
            start_index = start + 1

            identity_evidence = await self._build_identity_evidence(
                context=context,
                batch_panels=batch_panels,
                batch_paths=batch_paths,
                previous_memory=previous_memory,
                on_log=on_log,
            )
            stats.identity_ocr_ms += identity_evidence.ocr_elapsed_ms
            stats.identity_confirmed_count += len(identity_evidence.confirmed_names)

            prompt = self._build_unified_prompt(
                context=context,
                panel_count=len(batch_paths),
                start_index=start_index,
                previous_memory=previous_memory,
                identity_evidence=identity_evidence,
            )
            inline_data = [self._image_part(path) for path in batch_paths]

            self._log(
                on_log,
                "request",
                f"Processing Script Batch {batch_index + 1}/{total_batches}",
                json.dumps(
                    {
                        "panels": [panel.panelId for panel in batch_panels],
                        "promptLength": len(prompt),
                        "imageCount": len(batch_paths),
                        "continuityApplied": bool(previous_memory and previous_memory.summary),
                        "recentNames": previous_memory.recentNames if previous_memory else [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            self._log(
                on_log,
                "request",
                "Identity evidence prepared for current script batch.",
                json.dumps(
                    {
                        "candidatePool": identity_evidence.candidate_pool,
                        "confirmedNames": identity_evidence.confirmed_names,
                        "carryoverNames": identity_evidence.carryover_names,
                        "hasTextSignal": identity_evidence.has_text_signal,
                        "useNeutralFallback": identity_evidence.use_neutral_fallback,
                        "neutralFallbackReason": identity_evidence.neutral_fallback_reason,
                        "ocrLineCount": identity_evidence.ocr_line_count,
                        "ocrProvider": identity_evidence.ocr_provider,
                        "identityOcrMs": identity_evidence.ocr_elapsed_ms,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            raw_text, usage = await self._call_gemini(
                api_key=api_key,
                prompt=prompt,
                inline_data=inline_data,
                on_log=on_log,
                stats=stats,
            )
            raw_outputs.append(raw_text)
            stats.prompt_tokens += usage.get("prompt_tokens", 0)
            stats.candidates_tokens += usage.get("candidates_tokens", 0)
            stats.total_tokens += usage.get("total_tokens", 0)

            parsed = self._assert_batch_length(
                self._parse_json_array(raw_text, "script generation"),
                len(batch_paths),
                "script generation",
            )

            chunk_results: list[ScriptItem] = []
            for index, item in enumerate(parsed):
                expected_panel_index = start_index + index
                actual_panel_index = int(item.get("panel_index", expected_panel_index))
                if actual_panel_index != expected_panel_index:
                    raise RuntimeError(
                        f"Expected panel_index {expected_panel_index} but received {actual_panel_index}."
                    )
                chunk_results.append(
                    ScriptItem(
                        panel_index=actual_panel_index,
                        voiceover_text=str(item.get("voiceover_text", "")).strip(),
                    )
                )

            all_results.extend(chunk_results)
            previous_memory = self._build_story_memory(batch_index, context, chunk_results, previous_memory)
            story_memories.append(previous_memory)

            self._log(
                on_log,
                "result",
                f"Batch {batch_index + 1}/{total_batches} complete",
                json.dumps([item.model_dump() for item in chunk_results], ensure_ascii=False, indent=2),
            )

        return all_results, story_memories, "\n\n---\n\n".join(raw_outputs), stats

    async def _build_identity_evidence(
        self,
        *,
        context: ScriptContext,
        batch_panels: list[PanelReference],
        batch_paths: list[Path],
        previous_memory: StoryMemory | None,
        on_log: JobLogger | None,
    ) -> IdentityEvidence:
        candidate_pool = self._dedupe_names(
            [
                *(previous_memory.recentNames if previous_memory else []),
                *self._manual_known_names(context),
            ]
        )
        if not candidate_pool:
            return IdentityEvidence(
                candidate_pool=[],
                confirmed_names=[],
                carryover_names=[],
                has_text_signal=False,
                use_neutral_fallback=True,
                neutral_fallback_reason="no candidate names available",
            )

        if not self.settings.gemini_identity_experiment_enabled:
            return IdentityEvidence(
                candidate_pool=candidate_pool,
                confirmed_names=[],
                carryover_names=candidate_pool[:MAX_HINT_NAMES],
                has_text_signal=False,
                use_neutral_fallback=True,
                neutral_fallback_reason="identity OCR experiment disabled",
            )

        if self.identity_ocr_provider is None:
            return IdentityEvidence(
                candidate_pool=candidate_pool,
                confirmed_names=[],
                carryover_names=candidate_pool[:MAX_HINT_NAMES],
                has_text_signal=False,
                use_neutral_fallback=True,
                neutral_fallback_reason="identity OCR provider unavailable",
                ocr_provider=self.settings.gemini_identity_ocr_provider,
            )

        started_at = perf_counter()
        ocr_texts: list[str] = []
        ocr_line_count = 0
        has_text_signal = False
        provider_name = self.settings.gemini_identity_ocr_provider

        try:
            for panel, path in zip(batch_panels, batch_paths):
                result = await self.identity_ocr_provider.extract(path, panel.panelId)
                ocr_line_count += len(result.lines)
                if result.has_text or result.full_text.strip() or result.lines:
                    has_text_signal = True
                if result.full_text.strip():
                    ocr_texts.append(result.full_text)
                ocr_texts.extend(line.text for line in result.lines if line.text.strip())
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            self._log(
                on_log,
                "error",
                "Identity OCR experiment failed; falling back to carryover hints.",
                json.dumps(
                    {
                        "provider": provider_name,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            return IdentityEvidence(
                candidate_pool=candidate_pool,
                confirmed_names=[],
                carryover_names=candidate_pool[:MAX_HINT_NAMES],
                has_text_signal=False,
                use_neutral_fallback=True,
                neutral_fallback_reason="identity OCR experiment failed",
                ocr_provider=provider_name,
                ocr_elapsed_ms=elapsed_ms,
            )

        confirmed_names = [
            name
            for name in candidate_pool
            if any(self._contains_name(text, name) for text in ocr_texts)
        ][:MAX_HINT_NAMES]
        carryover_names = [name for name in candidate_pool if name not in confirmed_names][:MAX_HINT_NAMES]

        if confirmed_names:
            neutral_reason = ""
        elif has_text_signal:
            neutral_reason = "ocr text found but no candidate names were confirmed"
        else:
            neutral_reason = "no usable text signal in current batch"

        return IdentityEvidence(
            candidate_pool=candidate_pool,
            confirmed_names=confirmed_names,
            carryover_names=carryover_names,
            has_text_signal=has_text_signal,
            use_neutral_fallback=not confirmed_names,
            neutral_fallback_reason=neutral_reason,
            ocr_line_count=ocr_line_count,
            ocr_provider=provider_name,
            ocr_elapsed_ms=int((perf_counter() - started_at) * 1000),
        )

    async def _call_gemini(
        self,
        *,
        api_key: str,
        prompt: str,
        inline_data: list[dict] | None,
        on_log: JobLogger | None,
        stats: GenerationStats,
    ) -> tuple[str, dict]:
        current_model = self.settings.gemini_model
        client = self._create_openai_client(api_key=api_key)
        user_content = [{"type": "text", "text": prompt}]
        if inline_data:
            user_content.extend(inline_data)
        messages = [{"role": "user", "content": user_content}]
        self._log_payload(on_log, current_model, prompt, inline_data)

        for attempt in range(1, max(1, self.settings.gemini_retry_attempts) + 1):
            try:
                gate_wait_ms = 0
                if self.gemini_request_gate is None:
                    response = await self._send_chat_completion(client=client, model=current_model, messages=messages)
                else:
                    async with self.gemini_request_gate.request_slot(model=current_model, on_log=on_log) as reservation:
                        gate_wait_ms += reservation.waited_ms
                        response = await self._send_chat_completion(client=client, model=current_model, messages=messages)
                stats.throttle_wait_ms += gate_wait_ms
                return self._extract_response_text(response, current_model), {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "candidates_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }
            except Exception as exc:
                status_code = self._extract_status_code(exc)
                if status_code == 429:
                    stats.rate_limited_count += 1

                if not self._is_retryable_exception(exc) or attempt >= max(1, self.settings.gemini_retry_attempts):
                    self._log(
                        on_log,
                        "error",
                        self._format_error_message(current_model, exc),
                    )
                    raise RuntimeError(self._format_runtime_error(current_model, exc)) from exc

                stats.retry_count += 1
                retry_delay_ms = self._compute_retry_delay_ms(attempt, exc)
                if self.gemini_request_gate is not None and status_code in {429, 503}:
                    await self.gemini_request_gate.apply_cooldown(
                        wait_ms=max(self.settings.gemini_cooldown_on_429_ms, retry_delay_ms),
                        reason="transient provider failure",
                        model=current_model,
                        on_log=on_log,
                        status_code=status_code,
                    )

                self._log(
                    on_log,
                    "request",
                    "Retrying Gemini request after transient failure.",
                    json.dumps(
                        {
                            "attempt": attempt,
                            "nextAttempt": attempt + 1,
                            "statusCode": status_code,
                            "waitMs": retry_delay_ms,
                            "model": current_model,
                            "error": self._extract_error_message(exc),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
                await asyncio.sleep(retry_delay_ms / 1000)

        raise RuntimeError(f"Gemini request failed for {current_model}.")

    async def _send_chat_completion(self, *, client, model: str, messages: list[dict]):
        return await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.8,
            top_p=0.95,
            max_tokens=MAX_OUTPUT_TOKENS,
        )

    def _create_openai_client(self, *, api_key: str):
        return openai.AsyncOpenAI(
            api_key=api_key,
            base_url=self._build_base_url(),
            timeout=60.0,
            max_retries=0,
        )

    def _build_base_url(self) -> str | None:
        base_url = self.settings.gemini_api_endpoint
        if not base_url:
            return None
        if not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
            return f"{base_url.rstrip('/')}/v1"
        return base_url

    def _extract_response_text(self, response, current_model: str) -> str:
        if not response.choices or not response.choices[0].message.content:
            raise RuntimeError(f"Gemini returned an empty response for {current_model}.")
        content = response.choices[0].message.content
        if isinstance(content, str):
            return content

        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif hasattr(item, "text"):
                parts.append(str(item.text))

        text = "".join(parts).strip()
        if not text:
            raise RuntimeError(f"Gemini returned an empty response for {current_model}.")
        return text

    def _compute_retry_delay_ms(self, attempt: int, exc: Exception) -> int:
        retry_after_ms = self._extract_retry_after_ms(exc)
        if retry_after_ms is not None:
            return retry_after_ms

        base_delay = max(1, self.settings.gemini_retry_base_delay_ms)
        max_delay = max(base_delay, self.settings.gemini_retry_max_delay_ms)
        backoff = min(max_delay, base_delay * (2 ** max(0, attempt - 1)))
        jitter_multiplier = 1 + (random.random() * 0.25)
        return min(max_delay, int(backoff * jitter_multiplier))

    def _extract_retry_after_ms(self, exc: Exception) -> int | None:
        headers = getattr(getattr(exc, "response", None), "headers", None) or {}
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if not retry_after:
            return None

        try:
            return max(0, int(float(retry_after) * 1000))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(retry_after)
            except (TypeError, ValueError):
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            delta = parsed - datetime.now(timezone.utc)
            return max(0, int(delta.total_seconds() * 1000))

    def _is_retryable_exception(self, exc: Exception) -> bool:
        status_code = self._extract_status_code(exc)
        if status_code in RETRYABLE_STATUS_CODES:
            return True
        return isinstance(
            exc,
            (
                openai.APIConnectionError,
                openai.APITimeoutError,
                TimeoutError,
                ConnectionError,
                OSError,
            ),
        )

    def _extract_status_code(self, exc: Exception) -> int | None:
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        response = getattr(exc, "response", None)
        candidate = getattr(response, "status_code", None)
        return candidate if isinstance(candidate, int) else None

    def _extract_error_message(self, exc: Exception) -> str:
        message = getattr(exc, "message", None)
        return str(message or exc)

    def _format_error_message(self, current_model: str, exc: Exception) -> str:
        status_code = self._extract_status_code(exc)
        message = self._extract_error_message(exc)
        if status_code is not None:
            return f"OpenAI API error for model {current_model} ({status_code}): {message}"
        return f"Unexpected error for model {current_model}: {message}"

    def _format_runtime_error(self, current_model: str, exc: Exception) -> str:
        status_code = self._extract_status_code(exc)
        message = self._extract_error_message(exc)
        if status_code is not None:
            return f"OpenAI API Error ({status_code}) {current_model}: {message}"
        return f"{type(exc).__name__} {current_model}: {message}"

    def _image_part(self, path: Path) -> dict:
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        b64_str = image_to_base64(
            path,
            max_width=self.settings.vision_max_width,
            max_height=self.settings.vision_max_height,
        )
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64_str}"
            },
        }

    def _build_unified_prompt(
        self,
        *,
        context: ScriptContext,
        panel_count: int,
        start_index: int,
        previous_memory: StoryMemory | None,
        identity_evidence: IdentityEvidence,
    ) -> str:
        title = self._compact_summary(context.mangaName)
        setup_summary = self._compact_summary(context.summary)
        previous_summary = self._compact_summary(previous_memory.summary if previous_memory else "")
        language_label = "Vietnamese" if context.language == "vi" else "English"
        neutral_examples = (
            '"nam nhan", "co gai", "doi thu", "bong nguoi", or "ke kia"'
            if context.language == "vi"
            else '"the man", "the woman", "the opponent", "the figure", or "the other person"'
        )

        sections: list[str] = [
            f"You write final {language_label} manga recap narration for YouTube.",
            "Keep the narration fast, tense, compact, and dramatic.",
        ]
        if title or setup_summary:
            series_lines = ["Series context:"]
            if title:
                series_lines.append(f"- Manga title: {title}")
            if setup_summary:
                series_lines.append(f"- Setup summary: {setup_summary}")
            sections.append("\n".join(series_lines))
        if previous_summary:
            sections.append(
                "\n".join(
                    [
                        "Previous context:",
                        previous_summary,
                        "If the current images do not show a clear scene change, keep continuity with that context.",
                    ]
                )
            )
        if identity_evidence.confirmed_names:
            sections.append(
                "\n".join(
                    [
                        "Confirmed from visible text/dialogue in this batch:",
                        f"- {', '.join(identity_evidence.confirmed_names)}",
                    ]
                )
            )
        if identity_evidence.carryover_names:
            sections.append(
                "\n".join(
                    [
                        "Carryover names from previous chunk:",
                        f"- {', '.join(identity_evidence.carryover_names)}",
                        "Use these only as continuity hints, not as proof of identity in the current images.",
                    ]
                )
            )
        if identity_evidence.use_neutral_fallback:
            sections.append(
                "\n".join(
                    [
                        "Identity confidence is low for this batch.",
                        "Use neutral labels for people instead of names unless the visible dialogue in this batch clearly names them.",
                    ]
                )
            )
        sections.append(
            "\n".join(
                [
                    "Naming rules:",
                    "- Use a character name only when the current images or visible dialogue make the identity clear.",
                    "- Never treat carryover names as proof on their own.",
                    f"- If identity is unclear, use neutral labels such as {neutral_examples}.",
                ]
            )
        )
        sections.append(
            "\n".join(
                [
                    "Output rules:",
                    f"- Write direct final narration in {language_label}.",
                    '- No greeting, no intro, no outro, no "tap truoc", and no trailer-style filler.',
                    "- Do not invent identity, motive, outcome, or twist that the current images do not support.",
                    "- Keep sentences concise, high-rhythm, and easy for TTS.",
                    "- Prefer 1 to 2 short sentences per panel.",
                ]
            )
        )
        sections.append(
            "\n".join(
                [
                    "Return raw JSON only with this schema:",
                    "[",
                    "  {",
                    f'    "panel_index": {start_index},',
                    '    "voiceover_text": "..."',
                    "  }",
                    "]",
                ]
            )
        )
        sections.append(
            "\n".join(
                [
                    "Requirements:",
                    f"- Return exactly {panel_count} items for {panel_count} images.",
                    f"- panel_index starts at {start_index} and increases by 1.",
                    "- Every voiceover_text must read like a compelling recap line, not a dry description.",
                ]
            )
        )
        return "\n\n".join(section for section in sections if section.strip())

    def _build_story_memory(
        self,
        chunk_index: int,
        context: ScriptContext,
        items: list[ScriptItem],
        previous_memory: StoryMemory | None,
    ) -> StoryMemory:
        summary = self._summarize_batch(items)
        recent_names = self._extract_recent_names(context, items, previous_memory)
        return StoryMemory(chunkIndex=chunk_index, summary=summary, recentNames=recent_names)

    def _summarize_batch(self, items: list[ScriptItem]) -> str:
        narration = " ".join(item.voiceover_text.strip() for item in items[-2:] if item.voiceover_text.strip())
        if not narration:
            return ""
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", narration) if part.strip()]
        summary = sentences[0] if sentences else narration
        return self._compact_summary(summary)

    def _extract_recent_names(
        self,
        context: ScriptContext,
        items: list[ScriptItem],
        previous_memory: StoryMemory | None,
    ) -> list[str]:
        source_text = " ".join(item.voiceover_text for item in items)
        candidates = self._dedupe_names(
            [
                *(previous_memory.recentNames if previous_memory else []),
                *self._manual_known_names(context),
            ]
        )
        matched = [name for name in candidates if self._contains_name(source_text, name)]
        if matched:
            return matched[:MAX_RECENT_NAMES]

        if not previous_memory:
            setup_text = f"{context.summary} {context.mainCharacter}".strip()
            seeded = [name for name in self._manual_known_names(context) if self._contains_name(setup_text, name)]
            return seeded[:MAX_RECENT_NAMES]

        return []

    def _manual_known_names(self, context: ScriptContext) -> list[str]:
        name = " ".join(context.mainCharacter.split())
        return [name] if name else []

    def _dedupe_names(self, names: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for name in names:
            normalized = " ".join(name.split())
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
        return deduped

    def _contains_name(self, text: str, name: str) -> bool:
        if not text or not name:
            return False
        return bool(re.search(re.escape(name), text, flags=re.IGNORECASE))

    def _compact_summary(self, value: str | None) -> str:
        if not value:
            return ""
        compact = " ".join(value.split())
        if not compact:
            return ""
        words = compact.split()
        limited = " ".join(words[:MAX_MEMORY_WORDS]).strip()
        if len(limited) <= MAX_MEMORY_CHARS:
            return limited
        return limited[: MAX_MEMORY_CHARS - 3].rstrip() + "..."

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

    def _log_payload(
        self,
        on_log: JobLogger | None,
        current_model: str,
        prompt: str,
        inline_data: list[dict] | None,
    ) -> None:
        image_info = []
        if inline_data:
            for idx, item in enumerate(inline_data):
                if isinstance(item, dict) and "image_url" in item:
                    url = item["image_url"].get("url", "")
                    preview = url[:50] + "..." if len(url) > 50 else url
                    image_info.append({"index": idx, "type": "image_url", "preview": preview})

        self._log(
            on_log,
            "request",
            f"Sending request to AI server using model {current_model} with {len(image_info)} images.",
            json.dumps(
                {
                    "model": current_model,
                    "baseUrl": self._build_base_url(),
                    "payload_summary": {
                        "text_prompt_length": len(prompt),
                        "total_attachments": len(image_info),
                        "attachments": image_info,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _log(self, on_log: JobLogger | None, log_type: str, message: str, details: str | None = None) -> None:
        if on_log is not None:
            on_log(log_type, message, details)
