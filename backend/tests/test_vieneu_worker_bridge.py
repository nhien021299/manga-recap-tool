from __future__ import annotations

import sys
from pathlib import Path

from app.core.config import Settings
from app.services.vieneu_worker_bridge import VieneuTtsWorkerBridge


class DummyClient:
    def __init__(self) -> None:
        self.loaded: tuple[Path, bool] | None = None

    def _load_voices_from_file(self, file_path: Path, clear_existing: bool = False) -> None:
        self.loaded = (file_path, clear_existing)


def build_settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None).model_copy(
        update={
            "temp_root_raw": str(tmp_path / ".temp" / "jobs"),
            "tts_vieneu_voice_root_raw": str(tmp_path / ".models" / "vieneu-voices"),
        }
    )


def test_load_local_voice_overrides_uses_project_voice_manifest(tmp_path: Path):
    settings = build_settings(tmp_path)
    bridge = VieneuTtsWorkerBridge(settings)
    client = DummyClient()
    voices_root = settings.tts_vieneu_voice_root
    voices_root.mkdir(parents=True)
    voices_file = voices_root / "voices.json"
    voices_file.write_text(
        '{"default_voice":"voice_default","presets":{"voice_default":{"codes":[1,2,3],"text":"Xin chao"}}}',
        encoding="utf-8",
    )

    bridge._load_local_voice_overrides(client)

    assert client.loaded == (voices_file, False)


def test_load_local_voice_overrides_skips_when_manifest_missing(tmp_path: Path):
    settings = build_settings(tmp_path)
    bridge = VieneuTtsWorkerBridge(settings)
    client = DummyClient()

    bridge._load_local_voice_overrides(client)

    assert client.loaded is None


def test_get_provider_option_reads_presets_without_loading_model(monkeypatch, tmp_path: Path):
    settings = build_settings(tmp_path)
    bridge = VieneuTtsWorkerBridge(settings)
    voices_root = settings.tts_vieneu_voice_root
    voices_root.mkdir(parents=True)
    (voices_root / "voices.json").write_text(
        '{"default_voice":"voice_default","presets":{"voice_default":{"description":"Cached voice"}}}',
        encoding="utf-8",
    )

    def fail_if_loaded():
        raise AssertionError("model loader should not run for provider options")

    monkeypatch.setattr(bridge, "_ensure_model_loaded", fail_if_loaded)

    provider = bridge.get_provider_option("VieNeu-TTS-0.3B")

    assert provider.enabled is True
    assert provider.defaultVoiceKey == "voice_default"
    assert [voice.key for voice in provider.voices] == ["voice_default"]


def test_get_runtime_response_reports_actionable_missing_torch_error(monkeypatch, tmp_path: Path):
    settings = build_settings(tmp_path)
    bridge = VieneuTtsWorkerBridge(settings)

    def raise_missing_torch():
        exc = ModuleNotFoundError("No module named 'torch'")
        exc.name = "torch"
        raise exc

    monkeypatch.setattr(bridge, "_ensure_model_loaded", raise_missing_torch)

    runtime = bridge.get_runtime_response()

    assert runtime.isAvailable is False
    assert runtime.runtimePython == sys.executable
    assert runtime.startupError is not None
    assert "Missing Python dependency 'torch'" in runtime.startupError
    assert "pip install -r" in runtime.startupError
