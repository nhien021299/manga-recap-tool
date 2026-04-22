from __future__ import annotations

import io
import json
import logging
import sys
import threading
import time
from pathlib import Path

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
        self._voice_presets: list[dict[str, str]] = []
        self._voice_alias_manifest: dict[str, object] | None = None

    def _backend_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _requirements_path(self) -> Path:
        return self._backend_root() / "requirements.txt"

    def _vieneu_site_packages(self) -> Path:
        return self._backend_root() / ".bench" / "vieneu-venv" / "Lib" / "site-packages"

    def _runtime_python(self) -> str:
        return sys.executable

    def _install_hint(self) -> str:
        runtime_python = self._runtime_python()
        requirements = self._requirements_path()
        return f'"{runtime_python}" -m pip install -r "{requirements}"'

    def _format_runtime_error(self, exc: Exception) -> str:
        if isinstance(exc, ModuleNotFoundError) and exc.name:
            module_name = exc.name
            return (
                f"Missing Python dependency '{module_name}' for VieNeu TTS in '{self._runtime_python()}'. "
                f"Install backend requirements into that environment: {self._install_hint()}"
            )
        return str(exc)

    def _load_voice_presets_from_disk(self) -> list[dict[str, str]]:
        voices_file = self.settings.tts_vieneu_voice_root / "voices.json"
        if not voices_file.exists():
            return []

        try:
            payload = json.loads(voices_file.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse VieNeu voices manifest: %s", voices_file)
            return []

        presets = payload.get("presets")
        if not isinstance(presets, dict):
            return []

        resolved_presets: list[dict[str, str]] = []
        for preset_id, raw_meta in presets.items():
            if not isinstance(preset_id, str) or not preset_id.strip():
                continue
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            label = str(meta.get("label") or meta.get("description") or preset_id).strip() or preset_id
            resolved_presets.append({"id": preset_id.strip(), "label": label})
        return resolved_presets

    def get_provider_option(self, label: str) -> VoiceProviderOption:
        disk_presets = self._load_voice_presets_from_disk()
        if disk_presets:
            self._voice_presets = disk_presets

        resolved_default_voice_key = self._resolve_voice_key(self.settings.tts_vieneu_default_voice_key)
        voices: list[VoiceOption] = []
        for preset in self._voice_presets:
            preset_meta = VIENEU_PRESET_CATALOG.get(preset["id"])
            voices.append(
                VoiceOption(
                    key=preset["id"],
                    label=preset_meta.label if preset_meta else preset["label"],
                    provider="vieneu",
                    isAvailable=self.is_available(),
                    sampleRate=24000,
                    speakerCount=1,
                    quality="standard-0.3b",
                    description=(
                        preset_meta.description
                        if preset_meta
                        else "Cached VieNeu-TTS-0.3B preset generated from a local reference wav/txt pair."
                    ),
                    styleTag=preset_meta.style_tag if preset_meta else None,
                    sampleUrl=preset_meta.sample_url if preset_meta else None,
                    statusMessage=None,
                )
            )

        if voices and resolved_default_voice_key not in {voice.key for voice in voices}:
            resolved_default_voice_key = voices[0].key

        return VoiceProviderOption(
            id="vieneu",
            label=label,
            enabled=bool(self._voice_presets),
            defaultVoiceKey=resolved_default_voice_key,
            statusMessage=None if self._voice_presets else "VieNeu voice preset manifest is missing.",
            voices=voices,
        )

    def get_runtime_response(self) -> TtsRuntimeResponse:
        requested_runtime, resolved_runtime, fallback_active, supports_gpu, device_name = self._resolve_runtime_state()
        try:
            self._ensure_model_loaded()
        except Exception as exc:
            self._last_error = self._format_runtime_error(exc)

        return TtsRuntimeResponse(
            provider="vieneu",
            requestedRuntime=requested_runtime,
            resolvedRuntime=resolved_runtime,
            executionProvider=f"torch-{resolved_runtime}",
            fallbackActive=fallback_active,
            supportsGpu=supports_gpu,
            deviceName=device_name,
            platform="native",
            modelSource="huggingface",
            modelPath=self.settings.tts_vieneu_model_id,
            modelBundle=self.settings.tts_vieneu_model_id,
            runtimePython=self._runtime_python(),
            availableProviders=["cpu", "gpu"] if supports_gpu else ["cpu"],
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
            started_at = time.perf_counter()
            try:
                requested_voice_key = request.voiceKey or self.settings.tts_vieneu_default_voice_key
                resolved_voice_key = self._resolve_voice_key(requested_voice_key)
                text = request.text.strip()
                preview = text[:80].replace("\n", " ")
                logger.info(
                    "VieNeu generation started voiceKey=%s resolvedVoiceKey=%s chars=%s words=%s speed=%.2f preview=%r",
                    requested_voice_key,
                    resolved_voice_key,
                    len(text),
                    len(text.split()),
                    request.speed,
                    preview,
                )
                voice_data = client.get_preset_voice(resolved_voice_key)
                audio_array = client.infer(
                    text=text,
                    voice=voice_data,
                    temperature=self.settings.tts_vieneu_temperature,
                )
                wav_buffer = io.BytesIO()
                sf.write(wav_buffer, audio_array, getattr(client, "sample_rate", 24000), format="WAV")
                elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
                logger.info(
                    "VieNeu generation completed voiceKey=%s resolvedVoiceKey=%s chars=%s audioSamples=%s elapsedMs=%s",
                    requested_voice_key,
                    resolved_voice_key,
                    len(text),
                    len(audio_array),
                    elapsed_ms,
                )
                self._is_warm = True
                self._last_error = None
                return wav_buffer.getvalue()
            except Exception as exc:
                self._last_error = str(exc)
                elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
                logger.exception(
                    "VieNeu generation failed voiceKey=%s elapsedMs=%s",
                    request.voiceKey or self.settings.tts_vieneu_default_voice_key,
                    elapsed_ms,
                )
                raise RuntimeError(f"VieNeu generation failed: {exc}") from exc

    def _load_local_voice_overrides(self, client) -> None:
        voices_file = self.settings.tts_vieneu_voice_root / "voices.json"
        if not voices_file.exists():
            return

        load_from_file = getattr(client, "_load_voices_from_file", None)
        if not callable(load_from_file):
            logger.warning("VieNeu client does not support loading local voice presets: %s", voices_file)
            return

        load_from_file(voices_file)
        logger.info("Loaded local VieNeu voice presets from %s", voices_file)

    def _load_voice_alias_manifest(self) -> dict[str, object]:
        if self._voice_alias_manifest is not None:
            return self._voice_alias_manifest

        manifest_path = self.settings.tts_vieneu_voice_root / "clone-cache.json"
        if not manifest_path.exists():
            self._voice_alias_manifest = {}
            return self._voice_alias_manifest

        try:
            self._voice_alias_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load VieNeu voice alias manifest: %s", manifest_path)
            self._voice_alias_manifest = {}
        return self._voice_alias_manifest

    def _resolve_voice_key(self, requested_voice_key: str) -> str:
        candidate = requested_voice_key.strip() or self.settings.tts_vieneu_default_voice_key
        manifest = self._load_voice_alias_manifest()
        fallbacks = manifest.get("fallbacks")
        if isinstance(fallbacks, dict):
            fallback_value = fallbacks.get(candidate)
            if isinstance(fallback_value, str) and fallback_value.strip():
                return fallback_value.strip()
        return candidate

    def _resolve_runtime_state(self) -> tuple[str, str, bool, bool, str]:
        requested_runtime = self.settings.tts_runtime
        supports_gpu = False
        try:
            import torch

            supports_gpu = bool(torch.cuda.is_available())
        except Exception:
            supports_gpu = False

        if requested_runtime == "gpu":
            resolved_runtime = "gpu" if supports_gpu else "cpu"
        elif requested_runtime == "auto":
            resolved_runtime = "gpu" if supports_gpu else "cpu"
        else:
            resolved_runtime = "cpu"

        fallback_active = requested_runtime == "gpu" and resolved_runtime != "gpu"
        device_name = "CUDA GPU" if resolved_runtime == "gpu" else "CPU"
        return requested_runtime, resolved_runtime, fallback_active, supports_gpu, device_name

    def _ensure_model_loaded(self):
        if self._vieneu_client is not None:
            return self._vieneu_client

        with self._model_lock:
            if self._vieneu_client is not None:
                return self._vieneu_client

            try:
                try:
                    import torch  # noqa: F401
                except ModuleNotFoundError as exc:
                    raise RuntimeError(self._format_runtime_error(exc)) from exc

                try:
                    from vieneu import Vieneu  # type: ignore
                except ImportError:
                    venv_site = self._vieneu_site_packages()
                    if venv_site.exists() and str(venv_site) not in sys.path:
                        sys.path.insert(0, str(venv_site))
                    from vieneu import Vieneu  # type: ignore

                _requested_runtime, resolved_runtime, _fallback, _supports_gpu, _device_name = self._resolve_runtime_state()
                backbone_device = "gpu" if resolved_runtime == "gpu" else "cpu"
                self._vieneu_client = Vieneu(
                    mode="standard",
                    backbone_repo=self.settings.tts_vieneu_model_id,
                    backbone_device=backbone_device,
                )
                self._load_local_voice_overrides(self._vieneu_client)
                voices = self._vieneu_client.list_preset_voices()
                self._voice_presets = [{"label": desc, "id": name} for desc, name in voices]
                self._is_warm = True
                self._last_error = None
            except Exception as exc:
                self._last_error = self._format_runtime_error(exc)
                logger.exception("Failed to initialize VieNeu TTS")
                raise

        return self._vieneu_client
