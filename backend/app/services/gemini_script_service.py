from __future__ import annotations

import asyncio
import json
import mimetypes
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import perf_counter

import openai

from app.core.config import Settings
from app.models.api import ScriptJobOptions, ScriptJobResult
from app.models.domain import Metrics, PanelReference, RawOutputs, ScriptContext, ScriptItem, StoryMemory
from app.models.jobs import JobLogger, JobRecord
from app.services.gemini_request_gate import GeminiRequestGate
from app.utils.image_io import image_to_base64

MAX_OUTPUT_TOKENS = 8192
MAX_MEMORY_WORDS = 70
MAX_MEMORY_CHARS = 420
MAX_RECENT_NAMES = 3
MAX_HINT_NAMES = 2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class IdentityEvidence:
    candidate_pool: list[str]
    confirmed_names: list[str]
    carryover_names: list[str]
    locked_names: list[str]
    has_text_signal: bool
    use_neutral_fallback: bool
    neutral_fallback_reason: str


@dataclass
class GenerationStats:
    prompt_tokens: int = 0
    candidates_tokens: int = 0
    total_tokens: int = 0
    retry_count: int = 0
    rate_limited_count: int = 0
    throttle_wait_ms: int = 0
    batch_size_used: int = 0


class GeminiScriptService:
    def __init__(
        self,
        settings: Settings,
        *,
        gemini_request_gate: GeminiRequestGate | None = None,
    ) -> None:
        self.settings = settings
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
                "Gemini API key is not configured on the backend. Set AI_BACKEND_GEMINI_API_KEY in backend/.env."
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
                identityConfirmedCount=self._count_confirmed_character_mappings(context),
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

            identity_evidence = self._build_identity_evidence(
                context=context,
                previous_memory=previous_memory,
            )

            prompt = self._build_unified_prompt(
                context=context,
                batch_panels=batch_panels,
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

    def _build_identity_evidence(
        self,
        *,
        context: ScriptContext,
        previous_memory: StoryMemory | None,
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
                locked_names=[],
                has_text_signal=False,
                use_neutral_fallback=True,
                neutral_fallback_reason="no candidate names available",
            )

        locked_names = self._locked_character_names(context)
        return IdentityEvidence(
            candidate_pool=candidate_pool,
            confirmed_names=[],
            carryover_names=candidate_pool[:MAX_HINT_NAMES],
            locked_names=locked_names,
            has_text_signal=False,
            use_neutral_fallback=not bool(locked_names),
            neutral_fallback_reason="locked character mapping available" if locked_names else "using carryover hints only",
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
        batch_panels: list[PanelReference],
        panel_count: int,
        start_index: int,
        previous_memory: StoryMemory | None,
        identity_evidence: IdentityEvidence,
    ) -> str:
        title = self._compact_summary(context.mangaName)
        setup_summary = self._compact_summary(context.summary)
        previous_summary = self._compact_summary(previous_memory.summary if previous_memory else "")
        language_label = "Vietnamese" if context.language == "vi" else "English"
        narration_mode = self._infer_narration_mode(context, previous_memory)
        neutral_examples = (
            '"ga trai tre", "ong lao ao den", "nu sat thu", "ten linh canh", "ga thay tu", or "doi thu kia"'
            if context.language == "vi"
            else '"the man", "the woman", "the opponent", "the figure", or "the other person"'
        )
        mode_guide_map = {
            "horror": "Use dread, unease, and disturbing detail. Make the threat feel immediate and visceral.",
            "combat": "Use speed, impact, danger, and split-second reactions. Keep the energy sharp and forceful.",
            "escape": "Use urgency, pursuit, panic, and survival pressure. Make it feel like stopping means death.",
            "investigation": "Focus on clues, suspicion, evidence, and the danger hiding behind discovery.",
            "aftermath": "Use exhaustion, silence, damage, and lingering pressure without going flat.",
            "mystery": "Use curiosity, strange detail, hidden meaning, and unresolved danger.",
        }
        mode_guide = mode_guide_map.get(narration_mode, mode_guide_map["mystery"])

        sections: list[str] = [
            f"You write final {language_label} manga recap narration for YouTube.",
            "Your job is to maximize viewer retention.",
            "Every panel should create tension, curiosity, escalation, or emotional payoff.",
            "\n".join(
                [
                    "Current mode:",
                    f"- {narration_mode}",
                    f"- Mode behavior: {mode_guide}",
                ]
            ),
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
        character_guidance = self._build_character_guidance(context=context, batch_panels=batch_panels)
        if character_guidance:
            sections.append(character_guidance)
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
                    "Truth rules:",
                    "- Only describe what the current images support.",
                    "- Do not invent identity, motive, outcome, or twist that the current images do not support.",
                ]
            )
        )

        sections.append(
            "\n".join(
                [
                    "Compression rules:",
                    "- Default to the shortest phrasing that still sounds cinematic and clear.",
                    "- Remove filler transitions unless they add rhythm or contrast.",
                    "- Do not explain the same beat twice in different words.",
                    "- One panel, one narrative function: advance plot, intensify emotion, or create curiosity.",
                    "- When possible, imply dread or danger instead of fully spelling it out.",
                ]
            )
        )

        sections.append(
            "\n".join(
                [
                    "Naming rules:",
                    "- If a panel references a locked canonical name, always use that exact canonical name.",
                    "- If a panel references an unlocked display label, keep that same label stable across nearby panels unless stronger evidence appears.",
                    "- Use a character name only when the current images or visible dialogue make the identity clear.",
                    "- Never treat carryover names as proof on their own.",
                    "- If identity is unclear, label people by visible age, outfit, role, weapon, job, or standout physical traits before using a generic label.",
                    f"- Prefer specific neutral labels such as {neutral_examples}.",
                    '- Avoid overusing flat labels like "nam nhan" when the images support something more precise.',
                    "- If adjacent panels likely show the same unnamed person, keep the same descriptor unless the images clearly reveal better identity detail.",
                    "- Do not switch an unnamed character from one guessed role or job to another across nearby panels without strong visual proof.",
                    "- Do not infer a profession such as herb picker, worker, guard, or servant unless the current images make that role genuinely clear.",
                ]
            )
        )
        sections.append(
            "\n".join(
                [
                    "Output rules:",
                    f"- Write direct final narration in {language_label}.",
                    '- No greeting, no intro, no outro, no "tap truoc", and no trailer-style filler.',
                    "- Do not mechanically describe each image in isolation.",
                    "- Make adjacent panels flow like one seamless recap.",
                    "- Clearly establish the subject of the sentence to avoid pronoun confusion.",
                    "- Keep sentences concise, punchy, high-rhythm, and easy for TTS.",
                    "- Prefer 1 short sentence per panel. Use 2 short sentences only when the second sentence adds new tension, consequence, or curiosity.",
                    "- Compress wording by about 10-15% versus a normal recap style.",
                    "- Cut any phrase that only restates what is already obvious in the image.",
                    "- Do not narrate camera framing, pose, facial expression, clothing, or object placement unless that detail changes the plot, emotion, or danger.",
                    "- Focus on what is happening, what changes, and why it matters.",
                    "- If a sentence only describes the visible image without adding narrative value, rewrite or remove it.",
                    "- Vary rhythm: hit, breathe, then hit harder.",
                    "- Not every panel should sound maximum intensity.",
                    "- Add light curiosity when appropriate, but stay grounded in the images.",
                    "- Add a very light touch of modern Vietnamese Gen Z phrasing only when it sounds natural, brief, and does not break the current cinematic recap tone.",
                ]
            )
        )
        sections.append(
            "\n".join(
                [
                    "Lexical rules:",
                    "- Do not repeat the same emotional keywords across nearby panels unless the scene clearly escalates.",
                    '- Avoid generic lines like "mot canh tuong kinh hoang xuat hien" or equally vague phrasing.',
                    "- If a line feels generic, rewrite it to be more specific and engaging.",
                    "- Avoid repeatedly calling someone 'nam nhan' or an equally flat label when their look or role is visually clear.",
                    "- Prefer verbs and consequences over visual listing.",
                    "- Avoid opening too many lines with direct visual description such as 'truoc mat', 'luc nay', 'canh tuong nay', 'tren mat dat', 'phia truoc la'.",
                    "- Avoid redundant visual narration like describing blood, fear, darkness, weapons, or shock again if the same idea was already established in nearby panels.",
                    "- Any Gen Z flavor must stay subtle, short, and fully compatible with the current narration style.",
                ]
            )
        )
        sections.append(
            "\n".join(
                [
                    "Batch flow rules:",
                    "- Build momentum across the batch instead of treating each panel as equal.",
                    "- Save the strongest unresolved beat for the final line when the images support it.",
                    "- If the final panel suggests unresolved danger, discovery, confrontation, or a sudden change, end with a short cliffhanger-style line that pulls the viewer forward.",
                    "- The final line should raise tension or curiosity, not merely summarize what is visible.",
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
                    "- Every voiceover_text should flow logically into the next one as part of a continuous chapter recap.",
                    "- Across the batch, prioritize narrative compression over exhaustive visual description.",
                    "- The last 1-2 items should feel slightly more hook-driven when the scene supports it.",
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
        texts = [item.voiceover_text.strip() for item in items if item.voiceover_text.strip()]
        if not texts:
            return ""

        combined = " ".join(texts[-3:])
        combined = re.sub(r"\s+", " ", combined).strip()
        if not combined:
            return ""

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", combined) if part.strip()]
        if not sentences:
            return self._compact_summary(combined)

        if len(sentences) >= 2:
            summary = f"{sentences[0]} {sentences[-1]}"
        else:
            summary = sentences[0]

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

    def _infer_narration_mode(
        self,
        context: ScriptContext,
        previous_memory: StoryMemory | None,
    ) -> str:
        raw_text = " ".join(
            part
            for part in [
                context.summary or "",
                previous_memory.summary if previous_memory else "",
            ]
            if part
        ).lower()
        normalized_text = unicodedata.normalize("NFKD", raw_text)
        normalized_text = "".join(char for char in normalized_text if not unicodedata.combining(char))

        mode_keywords = {
            "horror": [
                "mau",
                "quy",
                "yeu quai",
                "xac",
                "chet",
                "kinh hoang",
                "ghe ron",
                "monster",
                "blood",
                "corpse",
                "demon",
                "horror",
                "red eye",
            ],
            "combat": [
                "chien",
                "danh",
                "kiem",
                "truy sat",
                "tan cong",
                "giao chien",
                "fight",
                "sword",
                "attack",
                "battle",
                "strike",
            ],
            "escape": [
                "chay",
                "tron",
                "thoat",
                "duoi",
                "hoang loan",
                "thuc mang",
                "escape",
                "flee",
                "run",
                "chase",
                "panic",
            ],
            "investigation": [
                "manh moi",
                "vat chung",
                "phong toa",
                "dieu tra",
                "kha nghi",
                "clue",
                "evidence",
                "investigate",
                "suspicious",
                "search",
            ],
            "aftermath": [
                "nguc",
                "xa lim",
                "tu",
                "kiet suc",
                "im lang",
                "hoi tho",
                "hoi suc",
                "prison",
                "cell",
                "silence",
                "exhausted",
                "aftermath",
            ],
            "mystery": [
                "bi mat",
                "ky la",
                "an",
                "la ky",
                "bi an",
                "mysterious",
                "strange",
                "hidden",
                "unknown",
                "weird",
            ],
        }

        scores = {
            mode: sum(1 for keyword in keywords if keyword in normalized_text)
            for mode, keywords in mode_keywords.items()
        }
        best_mode = max(scores, key=scores.get)
        return best_mode if scores[best_mode] > 0 else "mystery"

    def _manual_known_names(self, context: ScriptContext) -> list[str]:
        names: list[str] = []
        main_character = " ".join(context.mainCharacter.split())
        if main_character:
            names.append(main_character)
        if context.characterContext is not None:
            for character in context.characterContext.characters:
                canonical = " ".join(character.canonicalName.split())
                display = " ".join(character.displayLabel.split())
                if canonical:
                    names.append(canonical)
                elif display:
                    names.append(display)
        return names

    def _locked_character_names(self, context: ScriptContext) -> list[str]:
        if context.characterContext is None:
            return []
        return [
            character.canonicalName.strip()
            for character in context.characterContext.characters
            if character.lockName and character.canonicalName.strip()
        ]

    def _build_character_guidance(self, *, context: ScriptContext, batch_panels: list[PanelReference]) -> str:
        if context.characterContext is None or not context.characterContext.panelCharacterRefs:
            return ""

        character_by_id = {character.clusterId: character for character in context.characterContext.characters}
        lines = [
            "Character consistency rules:",
            "- If a panel references a character with a canonical name, always use that canonical name.",
            "- Do not rename the same character with a new descriptive label.",
            "- If no canonical name exists, use the provided display label consistently.",
            "- Only invent a new generic description when no character mapping is available.",
            "Panel character mapping for this batch:",
        ]
        has_mapping = False
        for panel in batch_panels:
            cluster_ids = context.characterContext.panelCharacterRefs.get(panel.panelId, [])
            if not cluster_ids:
                continue
            labels: list[str] = []
            for cluster_id in cluster_ids:
                character = character_by_id.get(cluster_id)
                if character is None:
                    continue
                preferred_label = character.canonicalName.strip() or character.displayLabel.strip()
                if not preferred_label:
                    continue
                labels.append(
                    f"{preferred_label}{' (locked)' if character.lockName and character.canonicalName.strip() else ''}"
                )
            if not labels:
                continue
            has_mapping = True
            lines.append(f"- Panel {panel.orderIndex + 1}: {', '.join(labels)}")

        return "\n".join(lines) if has_mapping else ""

    def _count_confirmed_character_mappings(self, context: ScriptContext) -> int:
        if context.characterContext is None:
            return 0
        return sum(1 for cluster_ids in context.characterContext.panelCharacterRefs.values() if cluster_ids)

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
