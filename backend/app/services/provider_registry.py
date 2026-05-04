from __future__ import annotations

from app.core.config import Settings


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_tts_providers(self) -> dict:
        return {}

    def warm_tts_runtime(self) -> None:
        pass

    def get_default_tts_runtime(self):
        return None

    def get_tts_runtime(self, provider_id: str | None = None):
        return None
