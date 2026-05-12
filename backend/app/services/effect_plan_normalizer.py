"""Normalizes compact Gemini effect plan into Remotion VideoDirection."""

import json
import logging
import re
from typing import Any

from app.constants.effect_whitelist import (
    ALLOWED_TRANSITIONS,
    ALLOWED_CODE_VFX,
    ALLOWED_COLOR_GRADES,
    ALLOWED_MOTIONS
)
from app.models.video import (
    BatchTtsResult,
    KeyframeEffect,
    NarrationPackage,
    SceneDirection,
    SceneTransition,
    TextOverlay,
    VideoDirection
)
from app.utils.dialogue_text import strip_duplicate_dialogue_from_narration

logger = logging.getLogger(__name__)

class EffectPlanNormalizer:
    @staticmethod
    def normalize_plan(
        raw_json: str,
        package: NarrationPackage,
        tts_result: BatchTtsResult,
        width: int,
        height: int,
        fps: int
    ) -> VideoDirection:
        # 1. Parse JSON
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(f"Normalizer failed to parse JSON: {exc}")
            raise ValueError("Invalid JSON") from exc

        items = parsed.get("items", [])
        if not items:
            logger.warning("Normalizer found no items, returning fallback")
            raise ValueError("No items in effect plan")

        tts_map = {r.scene: r for r in tts_result.scene_results}
        scenes: list[SceneDirection] = []

        # Convert list of scenes into dict for lookup
        scene_input_map = {s.scene: s for s in package.scenes}

        for item in items:
            if len(item) < 9:
                continue
            scene_num = item[0]
            scene_type = item[1]
            mood = item[2]
            motion = item[3]
            intensity = item[4]
            transition = item[5]
            duration = item[6]
            vfx = item[7]
            grade = item[8]

            # 2. Validation
            motion = motion if motion in ALLOWED_MOTIONS else "push_in_center"
            transition = transition if transition in ALLOWED_TRANSITIONS else "crossfade"
            grade = grade if grade in ALLOWED_COLOR_GRADES else "neutral"
            
            valid_vfx = []
            for tag in vfx:
                if tag in ALLOWED_CODE_VFX:
                    valid_vfx.append(tag)
                else:
                    logger.warning(f"Dropped unknown vfx tag: {tag}")
            
            # Limit to max 3 vfx tags
            valid_vfx = valid_vfx[:3]
            
            intensity = max(0.0, min(1.0, float(intensity)))

            scene_input = scene_input_map.get(scene_num)
            if not scene_input:
                continue

            tts = tts_map.get(scene_num)
            audio_ms = tts.audio_duration_ms if tts else 0
            dialogue_ms = (tts.dialogue_duration_ms or 0) if tts else 0
            total_audio_ms = audio_ms + dialogue_ms

            # Safe duration clamp
            target_ms = tts.target_duration_ms if tts else int(scene_input.duration_seconds * 1000)
            scene_duration_ms = max(target_ms, total_audio_ms + duration + 100)

            # Generate TextOverlays from scene input
            text_overlays = []
            
            # Narration
            if scene_input.narration:
                narration_text = strip_duplicate_dialogue_from_narration(
                    scene_input.narration,
                    scene_input.dialogue,
                    scene_input.dialogue_speaker,
                )

                if narration_text:
                    text_overlays.append(TextOverlay(
                        text=narration_text,
                        start_pct=0.05,
                        end_pct=0.95,
                        style="subtitle",
                        position="bottom_center"
                    ))
            
            # Dialogue
            if scene_input.dialogue:
                text_overlays.append(TextOverlay(
                    text=scene_input.dialogue,
                    start_pct=0.1,
                    end_pct=0.9,
                    style="dialogue_bubble",
                    position="center"
                ))

            # Rule chống sai mood
            if scene_type == "combat_action" and mood == "calm":
                mood = "tense"

            direction = SceneDirection(
                scene=scene_num,
                total_duration_ms=scene_duration_ms,
                audio_start_ms=0,
                keyframes=[
                    KeyframeEffect(
                        time_pct=0.0,
                        effect=motion,
                        intensity=intensity,
                        easing="ease_in_out"
                    )
                ],
                transition_in=None,
                transition_out=SceneTransition(type=transition, duration_ms=duration),
                text_overlays=text_overlays,
                color_grade=grade,
                motion_preset=motion,
                motion_intensity=intensity,
                vfx_tags=valid_vfx,
                sfx_tags=[], # Removed SFX for now
                mood=mood,
                scene_type=scene_type
            )
            scenes.append(direction)

        # Check missing scenes
        directed_scenes = {s.scene for s in scenes}
        for scene in package.scenes:
            if scene.scene not in directed_scenes:
                # Add default
                scenes.append(EffectPlanNormalizer._default_scene_direction(
                    scene, tts_map.get(scene.scene)
                ))

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
                "version": "v2_compact"
            }
        )

    @staticmethod
    def _default_scene_direction(scene_input, tts) -> SceneDirection:
        audio_ms = tts.audio_duration_ms if tts else 0
        target_ms = tts.target_duration_ms if tts else int(scene_input.duration_seconds * 1000)
        scene_duration_ms = max(target_ms, audio_ms + 500 + 100)

        text_overlays = []
        if scene_input.narration:
            narration_text = strip_duplicate_dialogue_from_narration(
                scene_input.narration,
                scene_input.dialogue,
                scene_input.dialogue_speaker,
            )
            if narration_text:
                text_overlays.append(TextOverlay(
                    text=narration_text,
                    start_pct=0.05,
                    end_pct=0.95,
                    style="subtitle",
                    position="bottom_center"
                ))

        return SceneDirection(
            scene=scene_input.scene,
            total_duration_ms=scene_duration_ms,
            audio_start_ms=0,
            keyframes=[
                KeyframeEffect(
                    time_pct=0.0,
                    effect="push_in_center",
                    intensity=0.7,
                    easing="ease_in_out"
                )
            ],
            transition_out=SceneTransition(type="crossfade", duration_ms=500),
            text_overlays=text_overlays,
            color_grade="neutral",
            motion_preset="push_in_center",
            motion_intensity=0.7,
            vfx_tags=[],
            sfx_tags=[],
            mood="neutral",
            scene_type="establishing"
        )
