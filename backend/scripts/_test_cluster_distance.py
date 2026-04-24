"""Test DINOv2 distances on actual Tâm Ma panels to verify character separation."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.characters.detector import CharacterCropDetector
from app.services.characters.embedder import CharacterCropEmbedder

PANEL_DIR = Path(r"D:\Manhwa Recap\Tâm Ma\chapter 1 cropped")

# Panels shown in "nhan vat 1" cluster from the screenshot: 6, 9, 14, 28, 31, 51
TEST_PANELS = [6, 9, 14, 28, 31, 51]


def main() -> None:
    settings = get_settings()
    detector = CharacterCropDetector(settings)
    embedder = CharacterCropEmbedder(
        settings.character_cache_root,
        dino_model_path=settings.character_dino_model_resolved_path,
        embed_device=settings.character_embed_device,
    )

    print(f"Embedder provider: {embedder._embedder_provider}")
    print(f"DINOv2 path: {embedder._dino_model_path}")
    print()

    crop_data: list[tuple[str, str, np.ndarray]] = []  # (panel_label, kind, vector)

    for panel_num in TEST_PANELS:
        panel_path = PANEL_DIR / f"scene-{panel_num:03d}.png"
        if not panel_path.exists():
            print(f"  SKIP panel {panel_num}: file not found")
            continue

        panel_id = f"panel-{panel_num}"
        detections = detector.detect(panel_id=panel_id, order_index=panel_num, path=panel_path)

        # Take the best face/head crop from each panel
        best = None
        for det in detections:
            if det.kind in ("face", "head"):
                if best is None or det.detection_score > best.detection_score:
                    best = det
        if best is None and detections:
            best = detections[0]  # fallback to best heuristic
        if best is None:
            print(f"  Panel {panel_num}: no detections")
            continue

        with Image.open(panel_path) as img:
            rgb = img.convert("RGB")
            x, y, w, h = best.bbox
            crop_img = rgb.crop((x, y, x + w, y + h))

        embedding = embedder.embed(
            chapter_id="tam-ma-ch1-test",
            crop_id=f"{panel_id}::crop",
            crop_kind=best.kind,
            crop_image=crop_img,
            cache_hint="test",
        )
        label = f"P{panel_num:02d}({best.kind})"
        crop_data.append((label, best.kind, embedding.vector))
        provider = embedding.diagnostics.get("provider", "?")
        dino_dim = embedding.diagnostics.get("dinoDimension", "N/A")
        fallback = embedding.diagnostics.get("dinoFallbackReason", "")
        print(f"  {label}: dim={embedding.vector.shape[0]}, provider={provider}, dino_dim={dino_dim}, fallback={fallback or 'NONE'}")

    print(f"\n=== Cosine Similarity Matrix ({len(crop_data)} crops) ===")
    labels = [item[0] for item in crop_data]
    vectors = np.stack([item[2] for item in crop_data])

    # Print header
    header = "          " + "  ".join(f"{l:>10}" for l in labels)
    print(header)

    for i, (label_i, _, vec_i) in enumerate(crop_data):
        row = f"{label_i:>10}"
        for j, (_, _, vec_j) in enumerate(crop_data):
            sim = float(np.dot(vec_i, vec_j))
            row += f"  {sim:>10.4f}"
        print(row)

    print("\n=== Distance Matrix (1 - similarity) ===")
    print(header)
    for i, (label_i, _, vec_i) in enumerate(crop_data):
        row = f"{label_i:>10}"
        for j, (_, _, vec_j) in enumerate(crop_data):
            dist = 1.0 - float(np.dot(vec_i, vec_j))
            row += f"  {dist:>10.4f}"
        print(row)


if __name__ == "__main__":
    main()
