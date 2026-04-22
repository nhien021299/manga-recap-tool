from __future__ import annotations

from pathlib import Path

from app.core.config import BACKEND_ROOT, Settings


def test_relative_tts_paths_resolve_from_backend_root():
    settings = Settings(_env_file=None)

    assert settings.temp_root == (BACKEND_ROOT / ".temp" / "jobs").resolve()
    assert settings.tts_vieneu_voice_root == (BACKEND_ROOT / ".models" / "vieneu-voices").resolve()
    assert settings.tts_vieneu_model_id == "pnnbao-ump/VieNeu-TTS-0.3B"
