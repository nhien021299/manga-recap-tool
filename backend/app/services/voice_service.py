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
        from app.utils.tts_adapter import (
            merge_dialogue_into_narration,
            normalize_tts_text,
            split_into_tts_chunks,
            concatenate_and_pad_audio,
            count_words
        )
        import logging
        logger = logging.getLogger(__name__)

        provider_id = (request.provider or self.default_provider).strip()
        provider = self.providers.get(provider_id)
        if provider is None:
            supported = ", ".join(self.providers.keys())
            raise ValueError(f"Unsupported TTS provider '{provider_id}'. Supported providers: {supported}")

        options = provider.get_options()
        if not options.enabled:
            detail = options.statusMessage or f"TTS provider '{provider_id}' is not available."
            raise FileNotFoundError(detail)

        # 1. Merge and Normalize
        raw_text = merge_dialogue_into_narration(request.text, request.dialogue, request.speaker)
        normalized_text = normalize_tts_text(raw_text)
        chunks = split_into_tts_chunks(normalized_text)
        
        word_count = count_words(normalized_text)
        log_msg = f">>> [TTS] provider={provider_id} voice={request.voiceKey} chunks={len(chunks)} words={word_count}"
        logger.info(log_msg)
        for ci, ct in enumerate(chunks, start=1):
            chunk_log = f"    chunk[{ci}/{len(chunks)}] ({count_words(ct)}w): {ct}"
            logger.info(chunk_log)

        # 2. Generate per chunk
        chunk_wavs = []
        for i, chunk_text in enumerate(chunks, start=1):
            chunk_request = request.model_copy(update={"text": chunk_text})
            # Clear dialogue/speaker for chunks to avoid infinite recursion or re-merging
            chunk_request.dialogue = None
            chunk_request.speaker = None
            
            wav_bytes = provider.generate_audio(chunk_request)
            chunk_wavs.append(wav_bytes)

        # 3. Concatenate
        return concatenate_and_pad_audio(
            chunk_wavs,
            start_pad_ms=150,
            end_pad_ms=600,
            internal_pause_ms=200
        )
