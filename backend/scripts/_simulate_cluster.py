"""Simulate full character prepass on Tâm Ma chapter 1 with updated thresholds."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.characters.detector import CharacterCropDetector
from app.services.characters.embedder import CharacterCropEmbedder
from app.services.characters.cluster import (
    CharacterClusterer,
    ClusterInputCrop,
    ANCHOR_DISTANCE_THRESHOLD,
    IDENTITY_USABLE_KINDS,
)
from app.services.characters.quality import CharacterCropQualityScorer

PANEL_DIR = Path(r"D:\Manhwa Recap\Tâm Ma\chapter 1 cropped")


def main() -> None:
    settings = get_settings()
    detector = CharacterCropDetector(settings)
    quality_scorer = CharacterCropQualityScorer()
    embedder = CharacterCropEmbedder(
        settings.character_cache_root,
        dino_model_path=settings.character_dino_model_resolved_path,
        embed_device=settings.character_embed_device,
    )
    clusterer = CharacterClusterer(
        clusterer=settings.character_clusterer,
        min_cluster_size=settings.character_min_cluster_size,
    )

    print(f"Embedder provider: {embedder._embedder_provider}")
    print(f"Anchor distance threshold: {ANCHOR_DISTANCE_THRESHOLD}")
    print(f"Identity usable kinds: {IDENTITY_USABLE_KINDS}")
    print()

    panel_files = sorted(PANEL_DIR.glob("scene-*.png"))
    print(f"Total panels: {len(panel_files)}")

    cluster_inputs: list[ClusterInputCrop] = []
    crop_info: dict[str, dict] = {}  # crop_id -> {panel_num, kind, ...}

    for panel_path in panel_files:
        panel_num = int(panel_path.stem.split("-")[1])
        panel_id = f"panel-{panel_num:03d}"

        detections = detector.detect(panel_id=panel_id, order_index=panel_num, path=panel_path)

        with Image.open(panel_path) as img:
            panel_image = img.convert("RGB")
            panel_rgb = np.asarray(panel_image, dtype=np.uint8)

            for det_idx, det in enumerate(detections, start=1):
                crop_id = f"{panel_id}::crop::{det_idx:02d}"
                x, y, w, h = det.bbox
                crop_img = panel_image.crop((x, y, x + w, y + h))

                quality = quality_scorer.score(
                    panel_rgb=panel_rgb,
                    bbox=det.bbox,
                    detection_score=det.detection_score,
                )

                if quality.bucket in {"good", "medium"} and det.kind != "accessory":
                    embedding = embedder.embed(
                        chapter_id="tam-ma-ch1-sim",
                        crop_id=crop_id,
                        crop_kind=det.kind,
                        crop_image=crop_img,
                        cache_hint="sim",
                    )
                    cluster_inputs.append(
                        ClusterInputCrop(
                            crop_id=crop_id,
                            panel_id=panel_id,
                            order_index=panel_num,
                            vector=embedding.vector,
                            quality_bucket=quality.bucket,
                            crop_kind=det.kind,
                        )
                    )
                    crop_info[crop_id] = {
                        "panel_num": panel_num,
                        "kind": det.kind,
                        "quality": quality.bucket,
                        "score": det.detection_score,
                        "provider": embedding.diagnostics.get("provider", "?"),
                    }

    print(f"\nTotal crops for clustering: {len(cluster_inputs)}")
    kinds_count = {}
    for ci in cluster_inputs:
        kinds_count[ci.crop_kind] = kinds_count.get(ci.crop_kind, 0) + 1
    print(f"By kind: {kinds_count}")

    anchors = [c for c in cluster_inputs if c.quality_bucket == "good" and c.crop_kind in IDENTITY_USABLE_KINDS]
    print(f"Anchor-eligible crops (good + face/head): {len(anchors)}")
    for a in anchors:
        info = crop_info[a.crop_id]
        print(f"  {a.crop_id}: panel={info['panel_num']}, kind={a.crop_kind}, quality={a.quality_bucket}, score={info['score']:.3f}")

    clusters, assignments = clusterer.cluster(cluster_inputs)

    print(f"\n=== CLUSTERS: {len(clusters)} ===")
    for cluster in clusters:
        member_panels = set()
        member_kinds = []
        for crop_id in cluster.member_crop_ids:
            if crop_id in crop_info:
                member_panels.add(crop_info[crop_id]["panel_num"])
                member_kinds.append(crop_info[crop_id]["kind"])
        print(f"\n  Cluster {cluster.cluster_index}: conf={cluster.confidence:.3f} | flags={cluster.review_flags}")
        print(f"    Anchor crops: {cluster.anchor_crop_ids}")
        print(f"    Member panels: {sorted(member_panels)}")
        print(f"    Member kinds: {member_kinds}")

    print(f"\n=== ASSIGNMENTS ===")
    for assignment in sorted(assignments, key=lambda a: (a.cluster_index or 99, a.crop_id)):
        info = crop_info.get(assignment.crop_id, {})
        panel = info.get("panel_num", "?")
        kind = info.get("kind", "?")
        print(f"  P{panel:>3} {kind:>10} -> cluster={assignment.cluster_index} state={assignment.state} score={assignment.score:.3f} margin={assignment.margin_score:.3f}")


if __name__ == "__main__":
    main()
