from __future__ import annotations

from app.core.config import Settings
from app.providers.ocr.paddleocr_provider import PaddleOCRProvider
from app.providers.llama_cpp_text import LlamaCppTextProvider
from app.providers.ollama_text import OllamaTextProvider
from app.providers.ollama_vision import OllamaVisionProvider


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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
        return PaddleOCRProvider(
            min_confidence=self.settings.ocr_min_confidence,
            max_text_lines=self.settings.ocr_max_text_lines,
            prefer_sfx=self.settings.ocr_prefer_sfx,
        )

    def get_identity_ocr_provider(self) -> PaddleOCRProvider | None:
        if not self.settings.gemini_identity_experiment_enabled:
            return None
        return PaddleOCRProvider(
            min_confidence=self.settings.gemini_identity_ocr_min_confidence,
            max_text_lines=self.settings.gemini_identity_ocr_max_text_lines,
            prefer_sfx=self.settings.ocr_prefer_sfx,
        )

    def get_provider_info(self) -> dict[str, object]:
        return {
            "textProvider": self.settings.text_provider,
            "textModel": self.settings.text_model,
            "visionProvider": self.settings.vision_provider,
            "visionModel": self.settings.vision_model,
            "ocrEnabled": self.settings.ocr_enabled,
            "ocrProvider": "paddleocr" if self.settings.ocr_enabled else "disabled",
        }
