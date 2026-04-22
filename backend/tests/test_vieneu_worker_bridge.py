from __future__ import annotations

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


def test_resolve_fallback_voice_key_uses_clone_cache_manifest(tmp_path: Path):
    settings = build_settings(tmp_path)
    bridge = VieneuTtsWorkerBridge(settings)
    voices_root = settings.tts_vieneu_voice_root
    voices_root.mkdir(parents=True)
    manifest_path = voices_root / "clone-cache.json"
    manifest_path.write_text(
        (
            '{"fallbacks":{"voice_2_clone":"voice_default"}}'
        ),
        encoding="utf-8",
    )

    fallback = bridge._resolve_voice_key("voice_2_clone")

    assert fallback == "voice_default"
