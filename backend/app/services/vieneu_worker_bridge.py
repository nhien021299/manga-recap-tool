from __future__ import annotations

import io
import logging
import threading

import soundfile as sf

from app.core.config import Settings
from app.models.api import TtsRuntimeResponse, VoiceGenerateRequest, VoiceOption, VoiceProviderOption
from app.services.voice_sample_catalog import VIENEU_PRESET_CATALOG

logger = logging.getLogger(__name__)


class VieneuTtsWorkerBridge:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._generation_lock = threading.Semaphore(settings.tts_max_concurrent_jobs)
        self._model_lock = threading.Lock()
        self._vieneu_client = None
        self._is_warm = False
        self._last_error: str | None = None
        self._voice_presets = []

    def get_provider_option(self, label: str) -> VoiceProviderOption:
        try:
            self._ensure_model_loaded()
        except Exception as e:
            self._last_error = str(e)
            
        voices = []
        for v in self._voice_presets:
            preset_meta = VIENEU_PRESET_CATALOG.get(v["id"])
            voices.append(VoiceOption(
                key=v["id"],
                label=preset_meta.label if preset_meta else v["label"],
                provider="vieneu",
                isAvailable=self.is_available(),
                sampleRate=24000,
                speakerCount=1,
                quality="turbo",
                description=preset_meta.description if preset_meta else "VieNeu V2 Turbo voice preset.",
                styleTag=preset_meta.style_tag if preset_meta else None,
                sampleUrl=preset_meta.sample_url if preset_meta else None,
                statusMessage=None
            ))

        default_voice_key = self.settings.tts_vieneu_default_voice_key
        if voices and default_voice_key not in {voice.key for voice in voices}:
            default_voice_key = voices[0].key
            
        return VoiceProviderOption(
            id="vieneu",
            label=label,
            enabled=self.is_available(),
            defaultVoiceKey=default_voice_key,
            statusMessage=self._last_error,
            voices=voices,
        )

    def get_runtime_response(self) -> TtsRuntimeResponse:
        return TtsRuntimeResponse(
            provider="vieneu",
            requestedRuntime=self.settings.tts_runtime,
            resolvedRuntime="cpu", # Turbo is typically CPU optimized
            executionProvider="native",
            fallbackActive=False,
            supportsGpu=False,
            deviceName="CPU (Turbo V2)",
            platform="native",
            modelSource="huggingface",
            modelBundle="turbo",
            runtimePython=None,
            availableProviders=["native"],
            warm=self._is_warm,
            isAvailable=self.is_available(),
            startupError=self._last_error,
        )

    def warm_up(self) -> None:
        self._ensure_model_loaded()
        smoke_text = self.settings.tts_smoke_test_text.strip()
        if smoke_text:
            self.generate_audio(
                VoiceGenerateRequest(
                    text=smoke_text,
                    provider="vieneu",
                    voiceKey=self.settings.tts_vieneu_default_voice_key,
                    speed=1.0,
                )
            )

    def is_available(self) -> bool:
        return self._last_error is None

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
        if not request.text.strip():
            raise ValueError("Voice generation text cannot be empty.")

        with self._generation_lock:
            client = self._ensure_model_loaded()
            try:
                voice_data = None
                if getattr(client, "get_preset_voice", None):
                    try:
                        voice_data = client.get_preset_voice(request.voiceKey or self.settings.tts_vieneu_default_voice_key)
                    except Exception:
                        pass
                
                if voice_data is not None:
                    audio_array = client.infer(text=request.text, voice=voice_data)
                else:
                    audio_array = client.infer(text=request.text)
                    
                wav_buffer = io.BytesIO()
                sf.write(wav_buffer, audio_array, getattr(client, "sample_rate", 24000), format="WAV")
                return wav_buffer.getvalue()

            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("Vieneu generation failed")
                raise RuntimeError(f"Vieneu generation failed: {exc}") from exc

    def _ensure_model_loaded(self):
        if self._vieneu_client is not None:
            return self._vieneu_client

        with self._model_lock:
            if self._vieneu_client is not None:
                return self._vieneu_client

            try:
                from vieneu import Vieneu # type: ignore
                self._vieneu_client = Vieneu()
                try:
                    voices = self._vieneu_client.list_preset_voices()
                    self._voice_presets = [{"label": desc, "id": name} for desc, name in voices]
                except Exception:
                    self._voice_presets = [{"label": "Default Viet", "id": "default"}]
                self._is_warm = True
                self._last_error = None
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("Failed to initialize Vieneu TTS")
                raise

        return self._vieneu_client
