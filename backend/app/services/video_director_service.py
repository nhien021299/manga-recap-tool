"""Gemini-powered video director service.

Sends scene data (images, narration, audio durations) to Gemini and receives
structured video direction: keyframes, camera motions, transitions, text
overlays, and color grading — all formatted for Remotion consumption.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import re
from pathlib import Path
from time import perf_counter

import openai

from app.core.config import Settings
from app.models.video import (
    BatchTtsResult,
    KeyframeEffect,
    NarrationPackage,
    SceneDirection,
    SceneTransition,
    TextOverlay,
    VideoDirection,
)
from app.services.gemini_request_gate import GeminiRequestGate
from app.utils.image_io import image_to_base64

logger = logging.getLogger(__name__)

EFFECTS_VOCABULARY = """
Scene Types (scene_type):
- establishing: Wide shots, landscapes, backgrounds.
- dialogue: Characters speaking.
- inner_thought: Character thinking, monologue.
- mystery_reveal: Discovery, secrets, omens.
- danger_build: Increasing danger, monsters appearing.
- combat_action: Fast action, fighting, chasing.
- shock_reveal: Shocking moments, blood, twists.
- emotional_pause: Quiet, sad, lonely moments.

Moods (mood):
- calm, ominous, tense, violent, tragic, mystical, lonely, epic.

Motion Presets (motion_preset):
- still_hold: Very slight zoom (for dialogue/calm).
- slow_zoom_in/slow_zoom_out: Classic slow motion.
- push_in_center: Stronger zoom into center.
- pan_left/pan_right/pan_up/pan_down: Directional movement.
- handheld_tension: Controlled camera shake for tension.
- impact_shake: Short sharp shake for hits/shocks.

Transitions (transition):
- crossfade: Standard smooth dissolve (400-800ms).
- dip_to_black: Fade to black (500-800ms).
- flash_cut: White flash (200-400ms).
- hard_cut: Instant cut (0ms).
- blur_fade: Blur then crossfade (400-600ms).

VFX Tags (vfx_tags): rain, cold_mist, fire_sparks, dark_smoke, etc.
SFX Tags (sfx_tags): dark_pulse, low_wind, blade_clash, heartbeat, etc.
""".strip()

MAX_OUTPUT_TOKENS = 16384


class VideoDirectorService:
    """Uses Gemini to generate professional video direction for Remotion."""

    def __init__(
        self,
        settings: Settings,
        *,
        gemini_request_gate: GeminiRequestGate | None = None,
    ) -> None:
        self.settings = settings
        self.gemini_request_gate = gemini_request_gate

    async def generate_direction(
        self,
        *,
        package: NarrationPackage,
        tts_result: BatchTtsResult,
        job_id: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
    ) -> VideoDirection:
        """Generate video direction by sending scene data to Gemini."""
        api_key = self.settings.effective_gemini_api_key
        if not api_key:
            raise RuntimeError(
                "Gemini API key is not configured. Set AI_BACKEND_GEMINI_API_KEY."
            )

        started = perf_counter()

        # Build the prompt
        prompt = self._build_prompt(
            package=package,
            tts_result=tts_result,
            width=width,
            height=height,
            fps=fps,
        )

        # Prepare scene image thumbnails for vision input
        image_parts = self._build_image_parts(package)

        logger.info(
            "Video director started job_id=%s scenes=%d images=%d prompt_chars=%d",
            job_id,
            len(package.scenes),
            len(image_parts),
            len(prompt),
        )

        # Call Gemini
        raw_text = await self._call_gemini(
            api_key=api_key,
            prompt=prompt,
            image_parts=image_parts,
        )

        # Parse the direction
        direction = self._parse_direction(
            raw_text=raw_text,
            package=package,
            tts_result=tts_result,
            width=width,
            height=height,
            fps=fps,
        )

        # Save to disk
        direction_dir = (
            self.settings.render_temp_root.parent / "video-jobs" / job_id / "direction"
        )
        direction_dir.mkdir(parents=True, exist_ok=True)
        direction_path = direction_dir / "video_direction.json"
        direction_path.write_text(
            direction.model_dump_json(indent=2),
            encoding="utf-8",
        )

        elapsed_ms = round((perf_counter() - started) * 1000)
        logger.info(
            "Video director completed job_id=%s total_duration_ms=%d elapsed_ms=%d. Plan saved at: %s",
            job_id,
            direction.total_duration_ms,
            elapsed_ms,
            direction_path,
        )

        return direction

    async def suggest_effects(
        self,
        *,
        package: NarrationPackage,
        style: str = "dark_xianxia_recap",
    ) -> list[dict]:
        """Suggest high-level effects (metadata only) using Gemini."""
        api_key = self.settings.effective_gemini_api_key
        if not api_key:
            raise RuntimeError("Gemini API key is not configured.")

        # Build prompt for suggestion only
        prompt = (
            "You are a professional video editor specializing in manhwa recap videos.\n"
            "Based on the following narration script and scene descriptions, suggest cinematic effects metadata for each scene.\n\n"
            f"Style: {style}\n\n"
            "Scenes:\n"
        )
        for s in package.scenes:
            prompt += f"- Scene {s.scene}: {s.narration[:150]}\n"
            if s.dialogue:
                prompt += f"  Dialogue: {s.dialogue}\n"

        prompt += (
            "\nAVAILABLE PRESETS:\n"
            f"{EFFECTS_VOCABULARY}\n\n"
            "Rules:\n"
            "- Gemini should only select metadata (presets, mood, intensity).\n"
            "- Return a JSON array of objects, one for each scene.\n"
            "- Required fields: scene, scene_type, mood, motion_preset, motion_intensity (0.1 to 1.0), transition, transition_duration_ms, vfx_tags (array), sfx_tags (array).\n"
            "Return ONLY the JSON array. No explanation."
        )

        image_parts = self._build_image_parts(package)
        
        raw_text = await self._call_gemini(
            api_key=api_key,
            prompt=prompt,
            image_parts=image_parts,
        )

        # Parse JSON
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Failed to parse suggested effects JSON from Gemini.")
            return []

    def _build_prompt(
        self,
        *,
        package: NarrationPackage,
        tts_result: BatchTtsResult,
        width: int,
        height: int,
        fps: int,
    ) -> str:
        """Build the Gemini prompt for video direction generation."""

        # Build scene timing table
        tts_map = {r.scene: r for r in tts_result.scene_results}
        scene_lines: list[str] = []
        for scene in package.scenes:
            tts = tts_map.get(scene.scene)
            audio_ms = tts.audio_duration_ms if tts else 0
            dialogue_ms = tts.dialogue_duration_ms if tts else 0
            target_ms = tts.target_duration_ms if tts else int(scene.duration_seconds * 1000)
            scene_lines.append(
                f"  Scene {scene.scene:02d}: \"{scene.title}\"\n"
                f"    Narration: \"{scene.narration[:100]}...\"\n"
                f"    Audio duration: {audio_ms}ms"
                + (f" + {dialogue_ms}ms dialogue" if dialogue_ms else "")
                + f"\n    Target visual duration: {target_ms}ms\n"
                f"    Has dialogue: {'yes' if scene.dialogue else 'no'}\n"
                f"    Retention beat: {scene.retention_beat or 'none'}"
            )
            if scene.scene_type:
                scene_lines[-1] += f"\n    Preset Suggestion: {scene.scene_type} ({scene.mood}), motion: {scene.motion_preset} (intensity: {scene.motion_intensity}), vfx: {scene.vfx_tags}"

        scene_block = "\n".join(scene_lines)

        tone_desc = ""
        if package.narration_style:
            tone_desc = (
                f"Narration tone: {package.narration_style.tone}\n"
                f"Pacing: {package.narration_style.pacing}"
            )

        sections: list[str] = [
            "You are a professional video editor and motion graphics director specializing in dark xianxia manhwa recap videos for YouTube.",
            "",
            "Your task: Create a complete video direction plan for a chapter recap video.",
            f"Output resolution: {width}×{height} (16:9 horizontal YouTube)",
            f"Frame rate: {fps}fps",
            f"Source images are vertical 9:16 manhwa scenes that will be composed into the horizontal frame.",
            "",
            f"Project: {package.project} — Chapter {package.chapter}",
            tone_desc,
            "",
            "IMPORTANT COMPOSITION NOTE:",
            "The source scene images are VERTICAL (9:16 aspect ratio).",
            "The output video is HORIZONTAL (16:9).",
            "Design your camera motions knowing the main scene image will be centered",
            "with cinematic blurred/darkened background fill on the sides.",
            "Ken Burns and zoom effects work on the centered main image.",
            "",
            "Scene data (with actual TTS audio durations):",
            scene_block,
            "",
            "I am also sending you the scene images as visual context.",
            "Use the images to inform your creative decisions about:",
            "- Which scenes need dramatic camera motion vs. static hold",
            "- Where transitions should be hard cuts vs. soft crossfades",
            "- Color grading that matches the scene mood",
            "- Text overlay timing and placement",
            "",
            f"Available effects vocabulary:\n{EFFECTS_VOCABULARY}",
            "",
            "Direction rules:",
            "- Every scene MUST have at least one keyframe effect (camera motion).",
            "- Match the total_duration_ms per scene to be at least as long as the audio, with visual hold time added.",
            "- Use crossfade transitions by default. Use hard cuts for impact moments. Use fade_black for major scene shifts.",
            "- Add subtitle text overlays for ALL narration text (Vietnamese). Position: bottom_center.",
            "- Add dialogue_bubble overlays for dialogue lines if present.",
            "- Vary camera motions across scenes — don't use the same effect for consecutive scenes.",
            "- Build pacing: slower/calmer for emotional scenes, faster/more dynamic for action/tension.",
            "- The final 2-3 scenes should build to maximum tension (this is a cliffhanger chapter ending).",
            "- Color grade should match scene mood: warm for tribal/home scenes, cold for mystery/danger, dark_jade for cultivation.",
            "",
            "Return ONLY a valid JSON array of scene direction objects. No markdown, no explanation.",
            "Schema for each scene:",
            json.dumps(
                {
                    "scene": 1,
                    "total_duration_ms": 5000,
                    "audio_start_ms": 0,
                    "keyframes": [
                        {
                            "time_pct": 0.0,
                            "effect": "push_in_center",
                            "intensity": 0.7,
                            "easing": "ease_in_out",
                            "params": {},
                        }
                    ],
                    "transition_in": None,
                    "transition_out": {
                        "type": "crossfade",
                        "duration_ms": 500,
                        "params": {},
                    },
                    "text_overlays": [
                        {
                            "text": "Vietnamese narration text here",
                            "start_pct": 0.0,
                            "end_pct": 0.9,
                            "style": "subtitle",
                            "position": "bottom_center",
                        }
                    ],
                    "color_grade": "cold_blue",
                    "motion_preset": "push_in_center",
                    "scene_type": "mystery_reveal",
                    "mood": "ominous",
                    "motion_intensity": 0.55,
                    "vfx_tags": ["cold_mist"],
                    "sfx_tags": ["dark_pulse"],
                    "subtitle_mood": "ominous"
                },
                indent=2,
                ensure_ascii=False,
            ),
            "",
            f"Return exactly {len(package.scenes)} scene direction objects.",
        ]

        return "\n".join(sections)

    def _build_image_parts(self, package: NarrationPackage) -> list[dict]:
        """Build image parts for Gemini vision input."""
        parts: list[dict] = []
        for scene in package.scenes:
            if not scene.image_path:
                continue
            image_path = Path(scene.image_path)
            if not image_path.is_file():
                logger.warning(
                    "Scene %d image not found or not a file: %s", scene.scene, image_path
                )
                continue

            mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
            b64 = image_to_base64(image_path, max_width=384, max_height=682)
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                }
            )
        return parts

    async def _call_gemini(
        self,
        *,
        api_key: str,
        prompt: str,
        image_parts: list[dict],
    ) -> str:
        """Call Gemini API with the direction prompt and scene images."""
        base_url = self.settings.gemini_api_endpoint
        if base_url and not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
            base_url = f"{base_url.rstrip('/')}/v1"

        import httpx
        
        # Create a custom client to avoid SSL context issues on some Windows environments
        # especially when using a local HTTP proxy for Gemini.
        verify_ssl = not (base_url and base_url.startswith("http://127.0.0.1"))
        
        http_client = httpx.AsyncClient(
            verify=verify_ssl,
            timeout=120.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
            max_retries=0,
        )

        user_content: list[dict] = [{"type": "text", "text": prompt}]
        user_content.extend(image_parts)
        messages = [{"role": "user", "content": user_content}]

        max_attempts = max(1, self.settings.gemini_retry_attempts)
        for attempt in range(1, max_attempts + 1):
            try:
                if self.gemini_request_gate is not None:
                    async with self.gemini_request_gate.request_slot(
                        model=self.settings.gemini_model
                    ):
                        response = await client.chat.completions.create(
                            model=self.settings.gemini_model,
                            messages=messages,
                            temperature=0.7,
                            top_p=0.9,
                            max_tokens=MAX_OUTPUT_TOKENS,
                        )
                else:
                    response = await client.chat.completions.create(
                        model=self.settings.gemini_model,
                        messages=messages,
                        temperature=0.7,
                        top_p=0.9,
                        max_tokens=MAX_OUTPUT_TOKENS,
                    )

                content = response.choices[0].message.content
                if not content:
                    raise RuntimeError("Gemini returned empty response for video direction.")
                return content

            except Exception as exc:
                status_code = getattr(exc, "status_code", None)
                if attempt >= max_attempts or (
                    status_code is not None
                    and status_code not in {429, 500, 502, 503, 504}
                ):
                    raise RuntimeError(
                        f"Gemini video direction failed: {exc}"
                    ) from exc

                delay_ms = min(
                    self.settings.gemini_retry_max_delay_ms,
                    self.settings.gemini_retry_base_delay_ms * (2 ** (attempt - 1)),
                )
                logger.warning(
                    "Gemini video direction attempt %d/%d failed, retrying in %dms: %s",
                    attempt,
                    max_attempts,
                    delay_ms,
                    exc,
                )
                await asyncio.sleep(delay_ms / 1000)

        raise RuntimeError("Gemini video direction failed after all retries.")

    def _parse_direction(
        self,
        *,
        raw_text: str,
        package: NarrationPackage,
        tts_result: BatchTtsResult,
        width: int,
        height: int,
        fps: int,
    ) -> VideoDirection:
        """Parse Gemini's JSON output into a VideoDirection model."""
        # Strip markdown fences if present
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse video direction JSON: %s", exc)
            logger.debug("Raw Gemini output:\n%s", raw_text[:2000])
            # Fall back to generating default direction
            return self._build_fallback_direction(
                package=package,
                tts_result=tts_result,
                width=width,
                height=height,
                fps=fps,
            )

        if isinstance(parsed, dict) and "scenes" in parsed:
            scene_list = parsed["scenes"]
        elif isinstance(parsed, list):
            scene_list = parsed
        else:
            logger.warning("Unexpected Gemini output structure, using fallback.")
            return self._build_fallback_direction(
                package=package,
                tts_result=tts_result,
                width=width,
                height=height,
                fps=fps,
            )

        scenes: list[SceneDirection] = []
        for item in scene_list:
            try:
                scenes.append(SceneDirection(**item))
            except Exception as exc:
                logger.warning("Failed to parse scene direction: %s — %s", exc, item)
                continue

        # Ensure we have a direction for every scene
        tts_map = {r.scene: r for r in tts_result.scene_results}
        directed_scenes = {s.scene for s in scenes}
        for scene in package.scenes:
            if scene.scene not in directed_scenes:
                tts = tts_map.get(scene.scene)
                audio_ms = tts.audio_duration_ms if tts else 0
                target_ms = tts.target_duration_ms if tts else int(scene.duration_seconds * 1000)
                scenes.append(
                    self._default_scene_direction(
                        scene_num=scene.scene,
                        duration_ms=max(target_ms, audio_ms + 500),
                        narration=scene.narration,
                        scene_input=scene,
                    )
                )

        scenes.sort(key=lambda s: s.scene)
        total_ms = sum(s.total_duration_ms for s in scenes)

        return VideoDirection(
            chapter=package.chapter,
            total_duration_ms=total_ms,
            fps=fps,
            width=width,
            height=height,
            scenes=scenes,
            global_settings={
                "project": package.project,
                "language": package.language,
                "style": "dark_xianxia_recap",
            },
        )

    def _build_fallback_direction(
        self,
        *,
        package: NarrationPackage,
        tts_result: BatchTtsResult,
        width: int,
        height: int,
        fps: int,
    ) -> VideoDirection:
        """Build a sensible default direction when Gemini fails."""
        tts_map = {r.scene: r for r in tts_result.scene_results}
        motion_presets = [
            "push_in_center",
            "ken_burns_tl",
            "drift_left_to_right",
            "push_in_upper_focus",
            "ken_burns_br",
            "drift_right_to_left",
            "rise_up_focus",
            "pull_back_reveal",
        ]

        scenes: list[SceneDirection] = []
        for index, scene in enumerate(package.scenes):
            tts = tts_map.get(scene.scene)
            audio_ms = tts.audio_duration_ms if tts else 0
            target_ms = tts.target_duration_ms if tts else int(scene.duration_seconds * 1000)
            duration_ms = max(target_ms, audio_ms + 500)
            preset = motion_presets[index % len(motion_presets)]

            scenes.append(
                self._default_scene_direction(
                    scene_num=scene.scene,
                    duration_ms=duration_ms,
                    narration=scene.narration,
                    motion_preset=preset,
                    scene_input=scene,
                )
            )

        total_ms = sum(s.total_duration_ms for s in scenes)
        return VideoDirection(
            chapter=package.chapter,
            total_duration_ms=total_ms,
            fps=fps,
            width=width,
            height=height,
            scenes=scenes,
            global_settings={
                "project": package.project,
                "language": package.language,
                "style": "dark_xianxia_recap",
                "fallback": True,
            },
        )

    def _default_scene_direction(
        self,
        *,
        scene_num: int,
        duration_ms: int,
        narration: str,
        motion_preset: str = "push_in_center",
        scene_input: SceneInput | None = None,
    ) -> SceneDirection:
        """Create a single default scene direction."""
        # Use overrides from input if available
        preset = motion_preset
        intensity = 0.7
        vfx = []
        mood = None
        scene_type = None
        transition = "crossfade"
        trans_duration = 500
        
        if scene_input:
            if scene_input.motion_preset:
                preset = scene_input.motion_preset
            if scene_input.motion_intensity is not None:
                intensity = scene_input.motion_intensity
            if scene_input.vfx_tags:
                vfx = scene_input.vfx_tags
            if scene_input.mood:
                mood = scene_input.mood
            if scene_input.scene_type:
                scene_type = scene_input.scene_type
            if scene_input.transition:
                transition = scene_input.transition
            if scene_input.transition_duration_ms is not None:
                trans_duration = scene_input.transition_duration_ms

        return SceneDirection(
            scene=scene_num,
            total_duration_ms=duration_ms,
            audio_start_ms=0,
            keyframes=[
                KeyframeEffect(
                    time_pct=0.0,
                    effect=preset,
                    intensity=intensity,
                    easing="ease_in_out",
                ),
            ],
            transition_in=None,
            transition_out=SceneTransition(type=transition, duration_ms=trans_duration),
            text_overlays=[
                TextOverlay(
                    text=narration,
                    start_pct=0.05,
                    end_pct=0.95,
                    style="subtitle",
                    position="bottom_center",
                ),
            ],
            color_grade="neutral",
            motion_preset=preset,
            motion_intensity=intensity,
            vfx_tags=vfx,
            mood=mood,
            scene_type=scene_type,
            subtitle_mood=scene_input.subtitle_mood if scene_input else None,
        )
