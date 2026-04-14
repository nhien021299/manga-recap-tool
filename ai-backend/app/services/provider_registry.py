from __future__ import annotations

from app.core.config import Settings
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
        return OllamaVisionProvider(self.settings.vision_base_url, self.settings.vision_model)

    def get_provider_info(self) -> dict[str, str]:
        return {
            "textProvider": self.settings.text_provider,
            "textModel": self.settings.text_model,
            "visionProvider": self.settings.vision_provider,
            "visionModel": self.settings.vision_model,
        }
