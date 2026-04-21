from __future__ import annotations

import json
import logging
import subprocess
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.config import Settings
from app.models.api import TtsRuntimeResponse, VoiceGenerateRequest, VoiceOption, VoiceProviderOption
from app.services.voice_sample_catalog import F5_PRESET_CATALOG, VoicePresetMeta

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class F5ReferencePreset:
    key: str
    audio_path: Path
    text_path: Path


@dataclass(frozen=True)
class F5RuntimeState:
    requested_runtime: str
    resolved_runtime: str
    execution_provider: str
    fallback_active: bool
    supports_gpu: bool
    available_providers: list[str]
    model_bundle: str
    model_path: Path | None
    startup_error: str | None


class F5OnnxWorkerBridge:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._generation_lock = threading.Semaphore(settings.tts_max_concurrent_jobs)
        self._state_lock = threading.Lock()
        self._runtime_state: F5RuntimeState | None = None
        self._is_warm = False
        self._last_error: str | None = None
        self._worker_script = Path(__file__).resolve().parents[2] / "runtime" / "f5" / "f5_onnx_worker.py"

    def get_provider_option(self, label: str) -> VoiceProviderOption:
        state = self._probe_runtime()
        presets = self._list_presets()
        is_ready = state.model_path is not None and bool(presets) and state.startup_error is None
        return VoiceProviderOption(
            id="f5",
            label=label,
            enabled=is_ready,
            defaultVoiceKey=self.settings.tts_f5_default_voice_key,
            statusMessage=self._build_status_message(state, presets),
            voices=[
                self._build_voice_option(preset, is_ready)
                for preset in presets
            ],
        )

    def get_runtime_response(self) -> TtsRuntimeResponse:
        state = self._probe_runtime()
        is_ready = state.model_path is not None and bool(self._list_presets()) and state.startup_error is None
        return TtsRuntimeResponse(
            provider="f5",
            requestedRuntime=state.requested_runtime,
            resolvedRuntime=state.resolved_runtime,
            executionProvider=state.execution_provider,
            fallbackActive=state.fallback_active,
            supportsGpu=state.supports_gpu,
            deviceName="DirectML GPU" if state.execution_provider == "DmlExecutionProvider" else "CPU",
            platform="Windows worker",
            modelSource="huggingface-onnx-zip",
            modelPath=str(state.model_path) if state.model_path else None,
            modelBundle=state.model_bundle,
            runtimePython=str(self.settings.tts_f5_python),
            availableProviders=state.available_providers,
            warm=self._is_warm,
            isAvailable=is_ready,
            startupError=state.startup_error,
        )

    def warm_up(self) -> None:
        self._probe_runtime(force=True)
        self._is_warm = True
        smoke_text = self.settings.tts_smoke_test_text.strip()
        if smoke_text and self._list_presets():
            self.generate_audio(
                VoiceGenerateRequest(
                    text=smoke_text,
                    provider="f5",
                    voiceKey=self.settings.tts_f5_default_voice_key,
                    speed=1.0,
                )
            )

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
        if not request.text.strip():
            raise ValueError("Voice generation text cannot be empty.")

        state = self._probe_runtime()
        if state.model_path is None:
            raise FileNotFoundError(state.startup_error or "F5 runtime is not ready.")

        preset = self._resolve_preset(request.voiceKey)
        job_root = self.settings.temp_root.parent / "tts-f5"
        job_root.mkdir(parents=True, exist_ok=True)

        request_name = f"{preset.key}-{uuid4().hex}"
        input_json = job_root / f"{request_name}.input.json"
        output_json = job_root / f"{request_name}.output.json"
        output_wav = job_root / f"{request_name}.wav"
        input_json.write_text(
            json.dumps(
                {
                    "text": request.text,
                    "speed": request.speed,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        command = [
            str(self.settings.tts_f5_python),
            str(self._worker_script),
            "--mode",
            "generate",
            "--provider",
            state.execution_provider,
            "--bundle-dir",
            str(state.model_path),
            "--reference-audio",
            str(preset.audio_path),
            "--reference-text-file",
            str(preset.text_path),
            "--input-json",
            str(input_json),
            "--output-wav",
            str(output_wav),
            "--output-json",
            str(output_json),
        ]

        try:
            with self._generation_lock:
                try:
                    completed = subprocess.run(
                        command,
                        cwd=str(Path(__file__).resolve().parents[2]),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                        timeout=1800,
                    )
                except Exception as exc:
                    self._last_error = str(exc)
                    logger.exception("F5 worker execution failed")
                    raise RuntimeError(f"F5 worker execution failed: {exc}") from exc

            if completed.returncode != 0:
                stderr = completed.stderr.strip()
                stdout = completed.stdout.strip()
                detail = stderr or stdout or "Unknown F5 generation failure."
                self._last_error = detail
                raise RuntimeError(detail)

            metadata = {}
            if output_json.exists():
                metadata = json.loads(output_json.read_text(encoding="utf-8"))

            if not output_wav.exists():
                self._last_error = metadata.get("error") or "F5 worker did not produce an output WAV."
                raise RuntimeError(self._last_error)

            self._last_error = None
            self._is_warm = True
            return output_wav.read_bytes()
        finally:
            for path in (input_json, output_json, output_wav):
                try:
                    if path.exists():
                        path.unlink()
                except OSError:
                    logger.warning("Failed to clean temporary F5 artifact: %s", path)

    def _probe_runtime(self, force: bool = False) -> F5RuntimeState:
        with self._state_lock:
            if self._runtime_state is not None and not force:
                return self._runtime_state

            startup_error: str | None = None
            available_providers: list[str] = []
            requested_runtime = self.settings.tts_runtime
            supports_gpu = False

            if not self.settings.tts_f5_python.exists():
                startup_error = f"Missing F5 runtime python: {self.settings.tts_f5_python}"
            elif not self._worker_script.exists():
                startup_error = f"Missing F5 worker script: {self._worker_script}"
            else:
                probe_json = self.settings.temp_root.parent / "tts-f5-probe.json"
                command = [
                    str(self.settings.tts_f5_python),
                    str(self._worker_script),
                    "--mode",
                    "probe",
                    "--output-json",
                    str(probe_json),
                ]
                completed = subprocess.run(
                    command,
                    cwd=str(Path(__file__).resolve().parents[2]),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=120,
                )
                try:
                    if completed.returncode != 0 or not probe_json.exists():
                        startup_error = completed.stderr.strip() or completed.stdout.strip() or "F5 runtime probe failed."
                    else:
                        payload = json.loads(probe_json.read_text(encoding="utf-8"))
                        available_providers = payload.get("availableProviders", [])
                        supports_gpu = "DmlExecutionProvider" in available_providers
                finally:
                    try:
                        if probe_json.exists():
                            probe_json.unlink()
                    except OSError:
                        logger.warning("Failed to clean F5 probe artifact: %s", probe_json)

            desired_runtime = requested_runtime
            if desired_runtime == "auto":
                desired_runtime = "gpu" if supports_gpu else "cpu"
            execution_provider = "DmlExecutionProvider" if desired_runtime == "gpu" else "CPUExecutionProvider"

            fallback_active = False
            if desired_runtime == "gpu" and not supports_gpu:
                execution_provider = "CPUExecutionProvider"
                desired_runtime = "cpu"
                fallback_active = True
                startup_error = startup_error or "DmlExecutionProvider is unavailable. Falling back to CPU."

            bundle_name = self.settings.tts_f5_gpu_bundle if desired_runtime == "gpu" else self.settings.tts_f5_cpu_bundle
            bundle_path = self._ensure_bundle_dir(bundle_name)
            if bundle_path is None:
                startup_error = startup_error or (
                    f"Missing F5 ONNX bundle '{bundle_name}' under {self.settings.tts_f5_model_root}."
                )

            self._runtime_state = F5RuntimeState(
                requested_runtime=requested_runtime,
                resolved_runtime=desired_runtime,
                execution_provider=execution_provider,
                fallback_active=fallback_active,
                supports_gpu=supports_gpu,
                available_providers=available_providers,
                model_bundle=bundle_name,
                model_path=bundle_path,
                startup_error=startup_error,
            )
            return self._runtime_state

    def _ensure_bundle_dir(self, bundle_name: str) -> Path | None:
        bundle_dir = self.settings.tts_f5_model_root / bundle_name
        if bundle_dir.exists():
            return bundle_dir

        zip_path = self.settings.tts_f5_model_root / f"{bundle_name}.zip"
        if not zip_path.exists():
            fallback_zip = self.settings.tts_f5_model_root / "downloads" / f"{bundle_name}.zip"
            if fallback_zip.exists():
                zip_path = fallback_zip
        if not zip_path.exists():
            sibling_downloads = self.settings.tts_f5_model_root.parent / f"{self.settings.tts_f5_model_root.name}-downloads"
            fallback_zip = sibling_downloads / f"{bundle_name}.zip"
            if fallback_zip.exists():
                zip_path = fallback_zip

        if not zip_path.exists():
            return None

        bundle_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(bundle_dir)
        return bundle_dir

    def _list_presets(self) -> list[F5ReferencePreset]:
        root = self.settings.tts_f5_reference_root
        if not root.exists():
            return []

        presets: list[F5ReferencePreset] = []
        for audio_path in sorted(root.glob("*.wav")):
            text_path = audio_path.with_suffix(".txt")
            if text_path.exists():
                presets.append(
                    F5ReferencePreset(
                        key=audio_path.stem,
                        audio_path=audio_path,
                        text_path=text_path,
                    )
                )
        return presets

    def _resolve_preset(self, voice_key: str) -> F5ReferencePreset:
        presets = {preset.key: preset for preset in self._list_presets()}
        preset = presets.get(voice_key) or presets.get(self.settings.tts_f5_default_voice_key)
        if preset is None:
            available = ", ".join(sorted(presets.keys())) or "none"
            raise ValueError(f"Unknown F5 preset '{voice_key}'. Available presets: {available}")
        return preset

    def _build_status_message(self, state: F5RuntimeState, presets: list[F5ReferencePreset]) -> str | None:
        if state.startup_error:
            return state.startup_error
        if not presets:
            return f"Add reference WAV/TXT preset files under {self.settings.tts_f5_reference_root}."
        return None

    @staticmethod
    def _humanize_preset_key(value: str) -> str:
        return value.replace("_", " ").strip().title()

    def _build_voice_option(self, preset: F5ReferencePreset, is_ready: bool) -> VoiceOption:
        preset_meta = F5_PRESET_CATALOG.get(preset.key, self._fallback_preset_meta(preset.key))
        return VoiceOption(
            key=preset.key,
            label=preset_meta.label,
            provider="f5",
            isAvailable=is_ready,
            sampleRate=24000,
            speakerCount=1,
            quality="onnx",
            description=preset_meta.description,
            styleTag=preset_meta.style_tag,
            sampleUrl=preset_meta.sample_url,
            statusMessage=None,
        )

    def _fallback_preset_meta(self, key: str) -> VoicePresetMeta:
        humanized = self._humanize_preset_key(key)
        slug = humanized.lower().replace(" ", "-")
        return VoicePresetMeta(
            label=humanized,
            description="F5 ONNX preset using a local reference clip.",
            style_tag="custom",
            sample_url=f"/assets/voice-samples/f5/{slug}.wav",
        )
