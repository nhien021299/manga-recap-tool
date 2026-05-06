from __future__ import annotations

from app.models.api import VoiceGenerateRequest, VoiceOptionsResponse


class VoiceService:
    def __init__(self, default_provider: str, providers: dict) -> None:
        self.default_provider = default_provider
        self.providers = providers

    def get_options(self) -> VoiceOptionsResponse:
        if self.providers:
            provider_options = [provider.get_options() for provider in self.providers.values()]
            default_provider = self.default_provider if self.default_provider in self.providers else provider_options[0].id
            return VoiceOptionsResponse(defaultProvider=default_provider, providers=provider_options)

        from app.models.api import VoiceOption, VoiceProviderOption
        
        vietvoice = VoiceProviderOption(
            id="vietvoice",
            label="VietVoice (Local GPU)",
            enabled=True,
            defaultVoiceKey="voice_default",
            voices=[
                VoiceOption(
                    key="voice_default",
                    label="Giọng Kể Truyện",
                    provider="vietvoice",
                    isAvailable=True,
                    description="VietVoice base TTS model",
                    styleTag="Recap",
                    sampleUrl="/api/v1/assets/voice-samples/voice_default.wav"
                ),
                VoiceOption(
                    key="lat_radio",
                    label="Lát Radio",
                    provider="vietvoice",
                    isAvailable=True,
                    description="Giọng đọc truyền cảm chuyên cho podcast/radio",
                    styleTag="Emotional",
                    sampleUrl="/api/v1/assets/voice-samples/lat_radio.wav"
                )
            ]
        )
        return VoiceOptionsResponse(
            defaultProvider="vietvoice",
            providers=[vietvoice],
        )

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
        if self.providers:
            provider_id = (request.provider or self.default_provider).strip()
            provider = self.providers.get(provider_id)
            if provider is None:
                raise ValueError(f"Unsupported TTS provider '{provider_id}'.")
            options = provider.get_options()
            voice = next((item for item in options.voices if item.key == request.voiceKey), None)
            if not options.enabled or voice is None or not voice.isAvailable:
                raise FileNotFoundError(options.statusMessage or "Voice provider assets are not available.")
            return provider.generate_audio(request)

        from app.utils.tts_adapter import merge_dialogue_into_narration
        from app.services.tts.vietvoice.vietvoice_provider import get_vietvoice_service
        import logging
        import uuid
        
        logger = logging.getLogger(__name__)

        provider_id = (request.provider or self.default_provider).strip()
        if provider_id != "vietvoice":
            raise ValueError(f"Unsupported TTS provider '{provider_id}'. Supported providers: vietvoice")

        raw_text = merge_dialogue_into_narration(request.text, request.dialogue, request.speaker)
        logger.info(f">>> [TTS Preview] provider={provider_id} voice={request.voiceKey} text_len={len(raw_text)}")

        service = get_vietvoice_service()
        
        output_path = service.synthesize(
            text=raw_text,
            output_name="preview.wav",
            voice_key=request.voiceKey,
            job_id=None,
            speed=request.speed,
        )
        return output_path.read_bytes()

    def generate_batch_audio(self, requests: list[VoiceGenerateRequest]) -> list[bytes]:
        return [self.generate_audio(request) for request in requests]
