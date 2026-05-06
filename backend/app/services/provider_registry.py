from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

from app.core.config import Settings
from app.models.api import TtsRuntimeResponse


@dataclass
class TtsRuntime:
    settings: Settings

    def get_runtime_response(self) -> TtsRuntimeResponse:
        requested = self.settings.tts_runtime or "auto"
        resolved = "gpu" if requested in {"gpu", "directml"} else "cpu"
        return TtsRuntimeResponse(
            provider="vieneu",
            requestedRuntime=requested,
            resolvedRuntime=resolved,
            executionProvider="torch-gpu" if resolved == "gpu" else "torch-cpu",
            fallbackActive=False,
            supportsGpu=True,
            deviceName="GPU" if resolved == "gpu" else "CPU",
            platform=platform.platform(),
            modelSource="huggingface",
            modelPath=None,
            modelBundle="pnnbao-ump/VieNeu-TTS-0.3B",
            runtimePython=sys.executable,
            availableProviders=["vieneu"],
            warm=False,
            isAvailable=True,
            startupError=None,
        )


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tts_runtime = TtsRuntime(settings)

    def get_tts_providers(self) -> dict:
        return {}

    def warm_tts_runtime(self) -> None:
        pass

    def get_default_tts_runtime(self):
        return self._tts_runtime

    def get_tts_runtime(self, provider_id: str | None = None):
        normalized = (provider_id or "vieneu").strip().lower()
        if normalized not in {"vieneu", "vietvoice"}:
            raise ValueError(f"Unsupported TTS provider '{provider_id}'.")
        return self._tts_runtime
