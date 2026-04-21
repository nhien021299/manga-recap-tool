from __future__ import annotations

from app.models.api import VoiceGenerateRequest, VoiceOptionsResponse
from app.providers.tts.base import TTSProvider


class VoiceService:
    def __init__(self, default_provider: str, providers: dict[str, TTSProvider]) -> None:
        self.default_provider = default_provider
        self.providers = providers

    def get_options(self) -> VoiceOptionsResponse:
        return VoiceOptionsResponse(
            defaultProvider=self.default_provider,
            providers=[provider.get_options() for provider in self.providers.values()],
        )

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
        provider_id = (request.provider or self.default_provider).strip()
        provider = self.providers.get(provider_id)
        if provider is None:
            supported = ", ".join(self.providers.keys())
            raise ValueError(f"Unsupported TTS provider '{provider_id}'. Supported providers: {supported}")

        options = provider.get_options()
        if not options.enabled:
            detail = options.statusMessage or f"TTS provider '{provider_id}' is not available."
            raise FileNotFoundError(detail)

        return provider.generate_audio(request)
