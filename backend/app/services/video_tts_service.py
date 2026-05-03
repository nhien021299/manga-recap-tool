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
from app.utils.tts_adapter import (
    concatenate_and_pad_audio,
    count_words,
    merge_dialogue_into_narration,
    normalize_tts_text,
    split_into_tts_chunks,
)

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
        on_progress: callable[[int, str], None] | None = None,
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
            
            if on_progress:
                progress_pct = int(5 + (index / total_scenes) * 30)
                on_progress(progress_pct, f"Generating TTS for scene {index}/{total_scenes}: {scene.title}")

            started = time.perf_counter()

            narration_text = scene.narration or ""
            dialogue_text = scene.dialogue
            speaker_name = scene.dialogue_speaker
            
            # 1. Adapt text for TTS
            raw_text = merge_dialogue_into_narration(narration_text, dialogue_text, speaker_name)
            normalized_text = normalize_tts_text(raw_text)
            chunks = split_into_tts_chunks(normalized_text)

            word_count = count_words(" ".join(chunks))
            estimated_duration = word_count / 3.2 + 0.5
            
            # Warn if original duration is too short or dialogue is merged purely due to length
            if scene.duration_seconds < estimated_duration:
                logger.warning("[WARN] Scene %02d original duration too short for text density.", scene_num)
            
            if dialogue_text and count_words(dialogue_text) <= 4:
                logger.warning("[WARN] Scene %02d dialogue was merged because it has fewer than 5 words.", scene_num)

            logger.info(
                "TTS scene %d/%d (%s) chunks=%d words=%d estimated=%.1fs min=%.1fs",
                index,
                total_scenes,
                scene.title,
                len(chunks),
                word_count,
                estimated_duration,
                scene.duration_seconds
            )

            # 2. Generate audio per chunk
            chunk_wavs = []
            for chunk_idx, chunk_text in enumerate(chunks, start=1):
                if not chunk_text.strip():
                    continue
                tts_request = VoiceGenerateRequest(
                    text=chunk_text,
                    provider=request.provider,
                    voiceKey=request.voice_key,
                    speed=request.speed,
                )
                wav_bytes = self.voice_service.generate_audio(tts_request)
                chunk_wavs.append(wav_bytes)

            # 3. Concatenate and add padding
            final_wav_bytes = concatenate_and_pad_audio(
                chunk_wavs,
                start_pad_ms=150,
                end_pad_ms=600,
                internal_pause_ms=200
            )

            narration_audio_path = audio_dir / f"scene_{scene_num:02d}.wav"
            narration_audio_path.write_bytes(final_wav_bytes)

            # 4. Final duration logic
            narration_duration_ms = self._measure_audio_duration_ms(narration_audio_path)
            actual_duration_sec = narration_duration_ms / 1000.0
            
            final_scene_duration = max(scene.duration_seconds, actual_duration_sec + 0.4)
            final_duration_ms = int(final_scene_duration * 1000)

            visual_hold_ms = max(0, final_duration_ms - narration_duration_ms)

            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            
            # Spec logger output
            logger.info(
                "[Scene %02d] words=%d | min=%.1fs | estimated=%.1fs | actual=%.1fs | final=%.1fs | chunks=%d | status=OK",
                scene_num,
                word_count,
                scene.duration_seconds,
                estimated_duration,
                actual_duration_sec,
                final_scene_duration,
                len(chunks)
            )

            scene_results.append(
                SceneTtsResult(
                    scene=scene_num,
                    title=scene.title,
                    audio_path=str(narration_audio_path),
                    audio_duration_ms=narration_duration_ms,
                    target_duration_ms=final_duration_ms,
                    visual_hold_ms=visual_hold_ms,
                    narration=" ".join(chunks),
                    dialogue_audio_path=None,
                    dialogue_duration_ms=None,
                )
            )
            total_audio_ms += narration_duration_ms

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
