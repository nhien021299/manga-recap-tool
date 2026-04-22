from __future__ import annotations

from app.models.api import VoiceGenerateRequest, VoiceProviderOption
from app.services.vieneu_worker_bridge import VieneuTtsWorkerBridge


class VieneuTtsProvider:
    provider_id = "vieneu"

    def __init__(self, bridge: VieneuTtsWorkerBridge) -> None:
        self.bridge = bridge

    def get_options(self) -> VoiceProviderOption:
        return self.bridge.get_provider_option("VieNeu-TTS-0.3B")

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
        return self.bridge.generate_audio(request)
