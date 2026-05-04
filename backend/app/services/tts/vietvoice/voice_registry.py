from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VietVoiceReference:
    voice_key: str
    reference_audio: Path
    reference_text: str


class VietVoiceRegistry:
    def __init__(self, ref_root: Path):
        self.ref_root = ref_root

    def get(self, voice_key: str) -> VietVoiceReference:
        voice_dir = self.ref_root / voice_key
        reference_audio = voice_dir / "reference.wav"
        reference_text_path = voice_dir / "reference.txt"

        if not reference_audio.exists():
            raise FileNotFoundError(f"Missing reference audio: {reference_audio}")

        if not reference_text_path.exists():
            raise FileNotFoundError(f"Missing reference text: {reference_text_path}")

        reference_text = reference_text_path.read_text(encoding="utf-8").strip()
        if not reference_text:
            raise ValueError(f"Empty reference text: {reference_text_path}")

        return VietVoiceReference(
            voice_key=voice_key,
            reference_audio=reference_audio,
            reference_text=reference_text,
        )
