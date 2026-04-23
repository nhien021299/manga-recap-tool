from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import Settings
from app.models.characters import ChapterCharacterState, CharacterCluster, CharacterPanelReference, PanelCharacterRef
from app.services.characters.repository import CharacterStateRepository

PREPASS_VERSION = "heuristic-panel-v1"


@dataclass(frozen=True)
class PanelFingerprint:
    panel_id: str
    order_index: int
    full_hash: int
    center_hash: int
    dark_ratio: float
    edge_density: float
    histogram: list[float]


class CharacterPrepassService:
    def __init__(self, settings: Settings, repository: CharacterStateRepository) -> None:
        self.settings = settings
        self.repository = repository
        self.settings.character_cache_root.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        *,
        chapter_id: str,
        panels: list[CharacterPanelReference],
        file_paths: list[Path],
        force: bool = False,
    ) -> ChapterCharacterState:
        if len(panels) != len(file_paths):
            raise ValueError("Character prepass panel metadata count must match uploaded files.")

        chapter_content_hash = self._compute_content_hash(panels, file_paths)
        existing_state = self.repository.load(chapter_id)
        if existing_state is not None and existing_state.chapterContentHash == chapter_content_hash:
            return existing_state

        cache_path = self._cache_path(chapter_id, chapter_content_hash)
        if cache_path.exists() and not force:
            state = ChapterCharacterState.model_validate_json(cache_path.read_text(encoding="utf-8"))
            return self.repository.save(state)

        fingerprints = [self._fingerprint(panel, path) for panel, path in zip(panels, file_paths, strict=True)]
        state = self._build_state(chapter_id=chapter_id, chapter_content_hash=chapter_content_hash, fingerprints=fingerprints)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return self.repository.save(state)

    def _build_state(
        self,
        *,
        chapter_id: str,
        chapter_content_hash: str,
        fingerprints: list[PanelFingerprint],
    ) -> ChapterCharacterState:
        now = datetime.now(timezone.utc).isoformat()
        clusters: list[CharacterCluster] = []
        panel_refs: list[PanelCharacterRef] = []
        used_panel_ids: set[str] = set()
        assigned_panel_ids: set[str] = set()

        sorted_fingerprints = sorted(fingerprints, key=lambda item: item.order_index)
        panel_order = {fingerprint.panel_id: fingerprint.order_index for fingerprint in sorted_fingerprints}
        for fingerprint in sorted_fingerprints:
            if fingerprint.panel_id in used_panel_ids:
                continue

            matched = [fingerprint]
            for other in sorted_fingerprints:
                if other.panel_id == fingerprint.panel_id or other.panel_id in used_panel_ids:
                    continue
                if self._is_confident_match(fingerprint, other):
                    matched.append(other)

            if len(matched) < 2:
                continue

            matched = sorted(matched, key=lambda item: item.order_index)
            for item in matched:
                used_panel_ids.add(item.panel_id)
                assigned_panel_ids.add(item.panel_id)

            cluster_index = len(clusters) + 1
            confidence = round(self._cluster_confidence(matched), 2)
            cluster_id = f"char_{cluster_index:03d}"
            sample_panel_ids = [item.panel_id for item in matched]
            cluster = CharacterCluster(
                clusterId=cluster_id,
                chapterId=chapter_id,
                status="review_needed",
                displayLabel=f"nhan vat lap lai {cluster_index}",
                confidenceScore=confidence,
                occurrenceCount=len(sample_panel_ids),
                anchorPanelIds=sample_panel_ids[:4],
                samplePanelIds=sample_panel_ids[:8],
                reviewFlags=["review_needed", "auto"],
            )
            clusters.append(cluster)
            for item in matched:
                panel_refs.append(
                    PanelCharacterRef(
                        panelId=item.panel_id,
                        clusterIds=[cluster_id],
                        source="suggested",
                        confidenceScore=confidence,
                    )
                )

        for fingerprint in sorted_fingerprints:
            if fingerprint.panel_id in assigned_panel_ids:
                continue
            panel_refs.append(
                PanelCharacterRef(
                    panelId=fingerprint.panel_id,
                    clusterIds=[],
                    source="unknown",
                    confidenceScore=0.0,
                )
            )

        return ChapterCharacterState(
            chapterId=chapter_id,
            chapterContentHash=chapter_content_hash,
            prepassVersion=PREPASS_VERSION,
            generatedAt=now,
            updatedAt=now,
            needsReview=True,
            clusters=clusters,
            panelCharacterRefs=sorted(panel_refs, key=lambda item: panel_order.get(item.panelId, 0)),
        )

    def _compute_content_hash(self, panels: list[CharacterPanelReference], file_paths: list[Path]) -> str:
        digest = hashlib.sha1()
        for panel, path in zip(panels, file_paths, strict=True):
            digest.update(panel.panelId.encode("utf-8"))
            digest.update(str(panel.orderIndex).encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def _cache_path(self, chapter_id: str, chapter_content_hash: str) -> Path:
        safe_chapter_id = hashlib.sha1(chapter_id.encode("utf-8")).hexdigest()[:12]
        return self.settings.character_cache_root / safe_chapter_id / f"{chapter_content_hash}.json"

    def _fingerprint(self, panel: CharacterPanelReference, path: Path) -> PanelFingerprint:
        with Image.open(path) as image:
            grayscale = image.convert("L")
            resized = grayscale.resize((16, 16))
            resized_array = np.asarray(resized, dtype=np.float32)
            average = float(np.mean(resized_array))
            full_hash = self._binary_hash((resized_array > average).flatten())

            center_crop = grayscale.crop(
                (
                    grayscale.width * 0.2,
                    grayscale.height * 0.15,
                    grayscale.width * 0.8,
                    grayscale.height * 0.85,
                )
            ).resize((16, 16))
            center_array = np.asarray(center_crop, dtype=np.float32)
            center_hash = self._binary_hash((center_array > float(np.mean(center_array))).flatten())

            dark_ratio = float(np.mean(resized_array < 96))
            gradient_x = np.abs(np.diff(resized_array, axis=1)).mean() / 255.0
            gradient_y = np.abs(np.diff(resized_array, axis=0)).mean() / 255.0
            edge_density = float((gradient_x + gradient_y) / 2)
            histogram, _ = np.histogram(resized_array, bins=8, range=(0, 255), density=True)

        return PanelFingerprint(
            panel_id=panel.panelId,
            order_index=panel.orderIndex,
            full_hash=full_hash,
            center_hash=center_hash,
            dark_ratio=dark_ratio,
            edge_density=edge_density,
            histogram=[float(value) for value in histogram.tolist()],
        )

    def _binary_hash(self, values: np.ndarray) -> int:
        bits = "".join("1" if bool(value) else "0" for value in values)
        return int(bits, 2)

    def _hamming_distance(self, left: int, right: int) -> int:
        return (left ^ right).bit_count()

    def _is_confident_match(self, left: PanelFingerprint, right: PanelFingerprint) -> bool:
        if abs(left.dark_ratio - right.dark_ratio) > 0.08:
            return False
        if abs(left.edge_density - right.edge_density) > 0.05:
            return False
        histogram_delta = float(sum(abs(a - b) for a, b in zip(left.histogram, right.histogram, strict=True)))
        if histogram_delta > 0.12:
            return False
        if self._hamming_distance(left.full_hash, right.full_hash) > 28:
            return False
        if self._hamming_distance(left.center_hash, right.center_hash) > 20:
            return False
        return True

    def _cluster_confidence(self, items: list[PanelFingerprint]) -> float:
        if len(items) < 2:
            return 0.0
        distances: list[float] = []
        first = items[0]
        for item in items[1:]:
            full_similarity = 1 - (self._hamming_distance(first.full_hash, item.full_hash) / 256)
            center_similarity = 1 - (self._hamming_distance(first.center_hash, item.center_hash) / 256)
            histogram_similarity = max(0.0, 1 - sum(abs(a - b) for a, b in zip(first.histogram, item.histogram, strict=True)))
            distances.append((full_similarity * 0.4) + (center_similarity * 0.4) + (histogram_similarity * 0.2))
        return min(0.99, max(0.55, float(sum(distances) / len(distances))))
