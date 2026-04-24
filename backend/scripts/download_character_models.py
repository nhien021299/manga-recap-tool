"""Download character system models for Phase 2 (anime face) and Phase 4 (DINOv2).

Usage:
    python scripts/download_character_models.py

Downloads:
    - facebook/dinov2-small  -> .models/dinov2/
    - anime face detect ONNX -> .models/anime-face/
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODELS_ROOT = BACKEND_ROOT / ".models"


def download_dinov2() -> None:
    """Download DINOv2-small from HuggingFace and save locally."""
    target = MODELS_ROOT / "dinov2"
    target.mkdir(parents=True, exist_ok=True)

    marker = target / ".downloaded"
    if marker.exists():
        print(f"[dinov2] Already downloaded at {target}")
        return

    print("[dinov2] Downloading facebook/dinov2-small from HuggingFace...")
    try:
        from transformers import AutoModel, AutoImageProcessor

        model = AutoModel.from_pretrained("facebook/dinov2-small")
        processor = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
        model.save_pretrained(str(target))
        processor.save_pretrained(str(target))
        marker.write_text("ok", encoding="utf-8")
        print(f"[dinov2] Saved to {target}")
    except Exception as exc:
        print(f"[dinov2] ERROR: {exc}", file=sys.stderr)
        raise


def download_anime_face_onnx() -> None:
    """Download a lightweight anime face detector ONNX model."""
    target = MODELS_ROOT / "anime-face"
    target.mkdir(parents=True, exist_ok=True)
    onnx_path = target / "anime-face-detect.onnx"

    if onnx_path.exists():
        print(f"[anime-face] Already downloaded at {onnx_path}")
        return

    print("[anime-face] Downloading anime face detection ONNX model...")
    try:
        from huggingface_hub import hf_hub_download

        downloaded = hf_hub_download(
            repo_id="deepghs/anime_face_detection",
            filename="face_detect_v1.4_s/model.onnx",
            local_dir=str(target),
        )
        src = Path(downloaded)
        if src.exists() and src != onnx_path:
            shutil.copy2(src, onnx_path)
        print(f"[anime-face] Saved to {onnx_path}")
    except Exception as exc:
        print(f"[anime-face] ERROR: {exc}", file=sys.stderr)
        raise


def main() -> None:
    print(f"Models root: {MODELS_ROOT}")
    download_dinov2()
    download_anime_face_onnx()
    print("\nAll models downloaded successfully!")
    print("\nSet these in your .env:")
    print(f"  AI_BACKEND_CHARACTER_DINO_MODEL_PATH={MODELS_ROOT / 'dinov2'}")
    print(f"  AI_BACKEND_CHARACTER_EMBEDDER=hybrid-dinov2")
    print(f"  AI_BACKEND_CHARACTER_EMBED_DEVICE=cpu")


if __name__ == "__main__":
    main()
