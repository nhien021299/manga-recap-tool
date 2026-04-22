from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / ".bench" / "generate_all_samples.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_all_samples", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_project_default_sample_text_requires_existing_reference(tmp_path, monkeypatch):
    module = load_module()
    reference_root = tmp_path / "voice-cache"
    reference_root.mkdir(parents=True)
    monkeypatch.setattr(module, "VOICE_CACHE_ROOT", reference_root)

    try:
        module.build_project_default_sample_text()
    except FileNotFoundError as exc:
        assert "Missing project default voice text" in str(exc)
    else:
        raise AssertionError("Expected build_project_default_sample_text() to reject missing references.")


def test_build_project_default_sample_text_returns_full_reference(tmp_path, monkeypatch):
    module = load_module()
    reference_root = tmp_path / "voice-cache"
    reference_dir = reference_root / "voice_default"
    reference_dir.mkdir(parents=True)
    source = (
        "Sau khi cả gia đình thu thập xong vật tư và chuẩn bị trở về, "
        "không ai để ý rằng cậu em út đã lén lấy lại pin trên bàn."
    )
    (reference_dir / "reference.txt").write_text(source, encoding="utf-8")
    monkeypatch.setattr(module, "VOICE_CACHE_ROOT", reference_root)

    preview = module.build_project_default_sample_text()

    assert preview == source
