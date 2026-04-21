from __future__ import annotations

from app.core.config import Settings
from app.providers.llama_cpp_text import LlamaCppTextProvider
from app.providers.ollama_text import OllamaTextProvider
from app.providers.ollama_vision import OllamaVisionProvider
from app.providers.tts.base import TTSProvider
from app.providers.tts.f5_provider import F5TtsProvider
from app.providers.tts.vieneu_provider import VieneuTtsProvider
from app.services.f5_onnx_worker_bridge import F5OnnxWorkerBridge
from app.services.vieneu_worker_bridge import VieneuTtsWorkerBridge


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vieneu_runtime = VieneuTtsWorkerBridge(settings)
        self.f5_runtime = F5OnnxWorkerBridge(settings)

    def get_text_provider(self) -> OllamaTextProvider | LlamaCppTextProvider:
        if self.settings.text_provider == "llama_cpp":
            return LlamaCppTextProvider(self.settings.llama_cpp_base_url, self.settings.text_model)
        return OllamaTextProvider(self.settings.text_base_url, self.settings.text_model)

    def get_vision_provider(self) -> OllamaVisionProvider:
        return OllamaVisionProvider(
            self.settings.vision_base_url,
            self.settings.vision_model,
            timeout_seconds=self.settings.vision_timeout_seconds,
            timeout_retries=self.settings.vision_timeout_retries,
            retry_delay_seconds=self.settings.vision_retry_delay_seconds,
            max_width=self.settings.vision_max_width,
            max_height=self.settings.vision_max_height,
        )

    def get_ocr_provider(self) -> PaddleOCRProvider | None:
        if not self.settings.ocr_enabled:
            return None
        from app.providers.ocr.paddleocr_provider import PaddleOCRProvider

        return PaddleOCRProvider(
            min_confidence=self.settings.ocr_min_confidence,
            max_text_lines=self.settings.ocr_max_text_lines,
            prefer_sfx=self.settings.ocr_prefer_sfx,
        )

    def get_identity_ocr_provider(self) -> PaddleOCRProvider | None:
        if not self.settings.gemini_identity_experiment_enabled:
            return None
        from app.providers.ocr.paddleocr_provider import PaddleOCRProvider

        return PaddleOCRProvider(
            min_confidence=self.settings.gemini_identity_ocr_min_confidence,
            max_text_lines=self.settings.gemini_identity_ocr_max_text_lines,
            prefer_sfx=self.settings.ocr_prefer_sfx,
        )

    def get_tts_providers(self) -> dict[str, TTSProvider]:
        vieneu_provider = VieneuTtsProvider(self.vieneu_runtime)
        f5_provider = F5TtsProvider(self.f5_runtime)
        return {
            "vieneu": vieneu_provider,
            "f5": f5_provider,
        }

    def warm_tts_runtime(self) -> None:
        if self.settings.tts_provider == "vieneu" and self.settings.tts_warm_on_startup:
            self.vieneu_runtime.warm_up()
        elif self.settings.tts_provider == "f5" and self.settings.tts_warm_on_startup:
            self.f5_runtime.warm_up()

    def get_default_tts_runtime(self):
        if self.settings.tts_provider == "f5":
            return self.f5_runtime
        return self.vieneu_runtime

    def get_tts_runtime(self, provider_id: str | None = None):
        resolved_provider = (provider_id or self.settings.tts_provider).strip().lower()
        if resolved_provider == "f5":
            return self.f5_runtime
        if resolved_provider == "vieneu":
            return self.vieneu_runtime
        raise ValueError(f"Unsupported TTS provider '{resolved_provider}'. Supported providers: vieneu, f5")

    def get_provider_info(self) -> dict[str, object]:
        return {
            "textProvider": self.settings.text_provider,
            "textModel": self.settings.text_model,
            "visionProvider": self.settings.vision_provider,
            "visionModel": self.settings.vision_model,
            "ocrEnabled": self.settings.ocr_enabled,
            "ocrProvider": "paddleocr" if self.settings.ocr_enabled else "disabled",
        }
