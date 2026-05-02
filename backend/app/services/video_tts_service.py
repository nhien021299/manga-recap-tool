"""Batch TTS service for video production pipeline.

Generates per-scene audio files from a NarrationPackage, using the existing
VieNeu TTS infrastructure. Each scene gets its own .wav file tied to its
scene number, with accurate duration measurement for timing sync.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import soundfile as sf

from app.core.config import Settings
from app.models.api import VoiceGenerateRequest
from app.models.video import (
    BatchTtsRequest,
    BatchTtsResult,
    NarrationPackage,
    SceneTtsResult,
)
from app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)


class VideoTtsService:
    """Generates TTS audio for every scene in a narration package."""

    def __init__(self, settings: Settings, voice_service: VoiceService) -> None:
        self.settings = settings
        self.voice_service = voice_service

    def _video_jobs_root(self) -> Path:
        return self.settings.render_temp_root.parent / "video-jobs"

    def parse_narration_file(self, narration_path: str) -> NarrationPackage:
        """Parse a chapter narration TTS JSON file from disk."""
        path = Path(narration_path)
        if not path.exists():
            raise FileNotFoundError(f"Narration file not found: {path}")

        raw = json.loads(path.read_text(encoding="utf-8"))
        return NarrationPackage(**raw)

    def generate_batch(
        self,
        request: BatchTtsRequest,
        *,
        job_id: str,
    ) -> BatchTtsResult:
        """Generate TTS audio for all scenes in the narration package.

        Returns a BatchTtsResult with per-scene audio paths and durations.
        """
        package = self.parse_narration_file(request.narration_path)
        audio_dir = self._video_jobs_root() / job_id / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        scene_results: list[SceneTtsResult] = []
        total_audio_ms = 0
        total_scenes = len(package.scenes)

        logger.info(
            "Video TTS batch started job_id=%s scenes=%d voice_key=%s speed=%.2f",
            job_id,
            total_scenes,
            request.voice_key,
            request.speed,
        )

        for index, scene in enumerate(package.scenes, start=1):
            scene_num = scene.scene
            started = time.perf_counter()

            # Generate narration audio
            narration_audio_path = audio_dir / f"scene_{scene_num:02d}.wav"
            narration_text = scene.narration.strip()

            if not narration_text:
                logger.warning(
                    "Scene %d has empty narration, skipping TTS", scene_num
                )
                continue

            logger.info(
                "TTS scene %d/%d (%s) chars=%d",
                index,
                total_scenes,
                scene.title,
                len(narration_text),
            )

            tts_request = VoiceGenerateRequest(
                text=narration_text,
                provider=request.provider,
                voiceKey=request.voice_key,
                speed=request.speed,
            )

            wav_bytes = self.voice_service.generate_audio(tts_request)
            narration_audio_path.write_bytes(wav_bytes)
            narration_duration_ms = self._measure_audio_duration_ms(narration_audio_path)

            # Generate dialogue audio if dialogue exists
            dialogue_audio_path: str | None = None
            dialogue_duration_ms: int | None = None
            dialogue_text = (scene.dialogue or "").strip()

            if dialogue_text:
                dialogue_path = audio_dir / f"scene_{scene_num:02d}_dialogue.wav"
                
                # Single-voice distinction: prepend speaker name if available
                tts_dialogue_text = dialogue_text
                if scene.dialogue_speaker:
                    tts_dialogue_text = f"{scene.dialogue_speaker} nói: {dialogue_text}"
                
                dialogue_request = VoiceGenerateRequest(
                    text=tts_dialogue_text,
                    provider=request.provider,
                    voiceKey=request.voice_key,
                    speed=request.speed,
                )
                dialogue_wav = self.voice_service.generate_audio(dialogue_request)
                dialogue_path.write_bytes(dialogue_wav)
                dialogue_duration_ms = self._measure_audio_duration_ms(dialogue_path)
                dialogue_audio_path = str(dialogue_path)

            # Calculate timing
            target_ms = int(scene.duration_seconds * 1000)
            total_narration_ms = narration_duration_ms + (dialogue_duration_ms or 0)
            visual_hold_ms = max(0, target_ms - total_narration_ms)

            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.info(
                "TTS scene %d complete audio_ms=%d target_ms=%d hold_ms=%d elapsed_ms=%s",
                scene_num,
                narration_duration_ms,
                target_ms,
                visual_hold_ms,
                elapsed_ms,
            )

            scene_results.append(
                SceneTtsResult(
                    scene=scene_num,
                    title=scene.title,
                    audio_path=str(narration_audio_path),
                    audio_duration_ms=narration_duration_ms,
                    target_duration_ms=target_ms,
                    visual_hold_ms=visual_hold_ms,
                    narration=narration_text,
                    dialogue_audio_path=dialogue_audio_path,
                    dialogue_duration_ms=dialogue_duration_ms,
                )
            )
            total_audio_ms += narration_duration_ms + (dialogue_duration_ms or 0)

        logger.info(
            "Video TTS batch completed job_id=%s scenes=%d total_audio_ms=%d",
            job_id,
            len(scene_results),
            total_audio_ms,
        )

        return BatchTtsResult(
            job_id=job_id,
            total_scenes=len(scene_results),
            total_audio_duration_ms=total_audio_ms,
            scene_results=scene_results,
        )

    def _measure_audio_duration_ms(self, audio_path: Path) -> int:
        """Measure the actual duration of a WAV file in milliseconds."""
        info = sf.info(str(audio_path))
        return round(info.duration * 1000)
