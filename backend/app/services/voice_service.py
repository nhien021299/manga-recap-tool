from __future__ import annotations

from app.models.api import VoiceGenerateRequest, VoiceOptionsResponse


class VoiceService:
    def __init__(self, default_provider: str, providers: dict) -> None:
        self.default_provider = default_provider

    def get_options(self) -> VoiceOptionsResponse:
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
                    sampleUrl="/assets/voice-samples/voice_default.wav"
                )
            ]
        )
        return VoiceOptionsResponse(
            defaultProvider="vietvoice",
            providers=[vietvoice],
        )

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
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
        )
        return output_path.read_bytes()
