from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


@dataclass(frozen=True)
class VietVoiceConfig:
    repo_backend_root: Path
    provider: str
    runtime: str
    voice_key: str
    ref_root: Path
    output_root: Path
    ffmpeg_path: str
    max_chars_per_chunk: int
    short_sleep_seconds: float
    batch_sleep_every: int
    batch_sleep_seconds: float
    error_sleep_seconds: float

    @staticmethod
    def from_env(repo_backend_root: Path) -> "VietVoiceConfig":
        ref_root_raw = os.getenv(
            "AI_BACKEND_TTS_VIETVOICE_REF_ROOT",
            "app/services/tts/vietvoice/refs",
        )
        output_root_raw = os.getenv(
            "AI_BACKEND_TTS_VIETVOICE_OUTPUT_ROOT",
            ".temp/tts-vietvoice",
        )

        return VietVoiceConfig(
            repo_backend_root=repo_backend_root,
            provider=os.getenv("AI_BACKEND_TTS_PROVIDER", "vietvoice"),
            runtime=os.getenv("AI_BACKEND_TTS_VIETVOICE_RUNTIME", "directml"),
            voice_key=os.getenv("AI_BACKEND_TTS_VIETVOICE_VOICE_KEY", "voice_default"),
            ref_root=(repo_backend_root / ref_root_raw).resolve(),
            output_root=(repo_backend_root / output_root_raw).resolve(),
            ffmpeg_path=os.getenv("AI_BACKEND_RENDER_FFMPEG_PATH", "ffmpeg"),
            max_chars_per_chunk=_get_int("AI_BACKEND_TTS_VIETVOICE_MAX_CHARS_PER_CHUNK", 100),
            short_sleep_seconds=_get_float("AI_BACKEND_TTS_VIETVOICE_SHORT_SLEEP_SECONDS", 0.5),
            batch_sleep_every=_get_int("AI_BACKEND_TTS_VIETVOICE_BATCH_SLEEP_EVERY", 8),
            batch_sleep_seconds=_get_float("AI_BACKEND_TTS_VIETVOICE_BATCH_SLEEP_SECONDS", 3.0),
            error_sleep_seconds=_get_float("AI_BACKEND_TTS_VIETVOICE_ERROR_SLEEP_SECONDS", 12.0),
        )
