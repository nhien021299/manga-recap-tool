from __future__ import annotations

import hashlib
import time
from pathlib import Path
from threading import Lock
from typing import List, Optional

from .audio_joiner import AudioJoiner
from .text_chunker import VietnameseSafeTextChunker
from .vietvoice_config import VietVoiceConfig
from .voice_registry import VietVoiceRegistry

# Import the TTSEngine from the vendor directory we copied
from .vendor.vietvoicetts.core.tts_engine import TTSEngine


class VietVoiceService:
    def __init__(self, config: VietVoiceConfig):
        self.config = config
        self.registry = VietVoiceRegistry(config.ref_root)
        self.chunker = VietnameseSafeTextChunker(max_chars=config.max_chars_per_chunk)
        self.joiner = AudioJoiner(ffmpeg_path=config.ffmpeg_path)
        self.engine = TTSEngine()
        self.config.output_root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def synthesize(
        self,
        text: str,
        output_name: str,
        voice_key: Optional[str] = None,
        job_id: Optional[str] = None,
        speed: float = 1.0,
    ) -> Path:
        voice_key = voice_key or self.config.voice_key
        reference = self.registry.get(voice_key)
        chunks = self.chunker.chunk(text)

        if not chunks:
            raise ValueError("Empty TTS text after chunking.")

        safe_output_name = self._safe_output_name(output_name)
        # Include speed in hash if no job_id to avoid cache collisions on different speeds
        job_folder_name = job_id or self._hash_text(f"{voice_key}|{speed}|{text}")[:16]
        job_dir = self.config.output_root / job_folder_name
        job_dir.mkdir(parents=True, exist_ok=True)

        final_path = job_dir / safe_output_name

        if final_path.exists() and final_path.stat().st_size > 1000:
            return final_path

        with self._lock:
            # Set engine speed before synthesis
            self.engine.config.speed = speed
            
            chunk_paths: List[Path] = []

            for index, chunk in enumerate(chunks, start=1):
                chunk_path = job_dir / f"chunk_{index:03d}.wav"
                chunk_paths.append(chunk_path)

                if chunk_path.exists() and chunk_path.stat().st_size > 1000:
                    continue

                self._generate_chunk_with_retry(
                    chunk=chunk,
                    chunk_path=chunk_path,
                    reference_audio=str(reference.reference_audio),
                    reference_text=reference.reference_text,
                )

                time.sleep(self.config.short_sleep_seconds)

                if index % self.config.batch_sleep_every == 0:
                    time.sleep(self.config.batch_sleep_seconds)

            self.joiner.concat_wavs_44100_mono_loudnorm(chunk_paths, final_path)

        return final_path

    def _generate_chunk_with_retry(
        self,
        chunk: str,
        chunk_path: Path,
        reference_audio: str,
        reference_text: str,
    ) -> None:
        try:
            self.engine.synthesize(
                text=chunk,
                output_path=str(chunk_path),
                reference_audio=reference_audio,
                reference_text=reference_text,
            )
        except Exception:
            time.sleep(self.config.error_sleep_seconds)
            self.engine.synthesize(
                text=chunk,
                output_path=str(chunk_path),
                reference_audio=reference_audio,
                reference_text=reference_text,
            )

        if not chunk_path.exists() or chunk_path.stat().st_size <= 1000:
            raise RuntimeError(f"TTS chunk generation failed or produced invalid wav: {chunk_path}")

    def _safe_output_name(self, output_name: str) -> str:
        name = Path(output_name).name
        if not name.lower().endswith(".wav"):
            name += ".wav"
        return name

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
