from __future__ import annotations

from typing import Protocol

from app.models.api import VoiceGenerateRequest, VoiceProviderOption


class TTSProvider(Protocol):
    provider_id: str

    def get_options(self) -> VoiceProviderOption:
        ...

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
        ...
