from __future__ import annotations

from dataclasses import dataclass


SAMPLE_BASE_URL = "/assets/voice-samples"


@dataclass(frozen=True)
class VoicePresetMeta:
    label: str
    description: str
    style_tag: str
    sample_url: str


VIENEU_PRESET_CATALOG: dict[str, VoicePresetMeta] = {
    "voice_default": VoicePresetMeta(
        label="Voice Default",
        description="Preset chinh cua project cho VieNeu-TTS-0.3B, duoc cache san tu reference wav/txt va tai su dung cho moi request TTS.",
        style_tag="preset chinh",
        sample_url=f"{SAMPLE_BASE_URL}/vieneu/voice-default.wav",
    ),
}
