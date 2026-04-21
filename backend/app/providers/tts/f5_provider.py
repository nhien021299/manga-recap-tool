from __future__ import annotations

from app.models.api import VoiceGenerateRequest, VoiceProviderOption
from app.services.f5_onnx_worker_bridge import F5OnnxWorkerBridge


class F5TtsProvider:
    provider_id = "f5"

    def __init__(self, bridge: F5OnnxWorkerBridge) -> None:
        self.bridge = bridge

    def get_options(self) -> VoiceProviderOption:
        return self.bridge.get_provider_option("F5 TTS ONNX")

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
        return self.bridge.generate_audio(request)
