from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import Settings
from app.models.characters import (
    ChapterCharacterState,
    CharacterCandidateAssignment,
    CharacterCluster,
    CharacterCrop,
    CharacterPanelReference,
    PanelCharacterRef,
)
from app.services.characters.cluster import (
    ANCHOR_DISTANCE_THRESHOLD,
    FACE_ATTACH_MARGIN_THRESHOLD,
    FACE_ATTACH_SIMILARITY_THRESHOLD,
    GREEN_MARGIN_THRESHOLD,
    GREEN_SIMILARITY_THRESHOLD,
    SUGGEST_MARGIN_THRESHOLD,
    SUGGEST_SIMILARITY_THRESHOLD,
    CharacterClusterer,
    ClusterInputCrop,
)
from app.services.characters.detector import CharacterCropDetector
from app.services.characters.embedder import CharacterCropEmbedder
from app.services.characters.quality import CharacterCropQualityScorer
from app.services.characters.repository import CharacterStateRepository

PREPASS_VERSION = "character-hybrid-v3"


class CharacterPrepassService:
    def __init__(self, settings: Settings, repository: CharacterStateRepository) -> None:
        self.settings = settings
        self.repository = repository
        self.detector = CharacterCropDetector(settings)
        self.quality_scorer = CharacterCropQualityScorer()
        self.embedder = CharacterCropEmbedder(settings.character_cache_root)
        self.clusterer = CharacterClusterer(
            clusterer=settings.character_clusterer,
            min_cluster_size=settings.character_min_cluster_size,
        )
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
        if not force and self._is_reusable_state(existing_state, chapter_content_hash=chapter_content_hash):
            return existing_state

        cache_path = self._cache_path(chapter_id, chapter_content_hash)
        if cache_path.exists() and not force:
            cached_state = ChapterCharacterState.model_validate_json(cache_path.read_text(encoding="utf-8"))
            if self._is_reusable_state(cached_state, chapter_content_hash=chapter_content_hash):
                return self.repository.save(cached_state)

        state = self._build_state(chapter_id=chapter_id, chapter_content_hash=chapter_content_hash, panels=panels, file_paths=file_paths)
        if existing_state is not None:
            self._apply_manual_constraints(state=state, previous_state=existing_state)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return self.repository.save(state)

    def _build_state(
        self,
        *,
        chapter_id: str,
        chapter_content_hash: str,
        panels: list[CharacterPanelReference],
        file_paths: list[Path],
    ) -> ChapterCharacterState:
        now = datetime.now(timezone.utc).isoformat()
        panel_order = {panel.panelId: panel.orderIndex for panel in panels}
        crops: list[CharacterCrop] = []
        cluster_inputs: list[ClusterInputCrop] = []
        panel_diagnostics: dict[str, object] = {}

        for panel, path in zip(panels, file_paths, strict=True):
            with Image.open(path) as image:
                panel_image = image.convert("RGB")
                panel_rgb = np.asarray(panel_image, dtype=np.uint8)
                detections = self.detector.detect(panel_id=panel.panelId, order_index=panel.orderIndex, path=path)
                panel_diagnostics[panel.panelId] = {
                    "detectedCropCount": len(detections),
                    "detectorVersion": self.detector.version,
                    "detectorMode": self.settings.character_detector_mode,
                    "detectorRuntime": self._detector_runtime_diagnostics(),
                }
                for detection_index, detection in enumerate(detections, start=1):
                    crop_id = f"{panel.panelId}::crop::{detection_index:02d}"
                    x, y, w, h = detection.bbox
                    crop_image = panel_image.crop((x, y, x + w, y + h))
                    quality = self.quality_scorer.score(
                        panel_rgb=panel_rgb,
                        bbox=detection.bbox,
                        detection_score=detection.detection_score,
                    )
                    cache_hint = ":".join(
                        [
                            self.detector.version,
                            detection.detector_source,
                            detection.detector_model,
                            detection.kind,
                            self.settings.character_detector_mode,
                            self.settings.character_device,
                            self.settings.character_object_model,
                            self.quality_scorer.version,
                            str(x),
                            str(y),
                            str(w),
                            str(h),
                            quality.bucket,
                            str(quality.score),
                        ]
                    )
                    embedding = None
                    if quality.bucket in {"good", "medium"} and detection.kind != "accessory":
                        embedding = self.embedder.embed(
                            chapter_id=chapter_id,
                            crop_id=crop_id,
                            crop_kind=detection.kind,
                            crop_image=crop_image,
                            cache_hint=cache_hint,
                        )
                        cluster_inputs.append(
                            ClusterInputCrop(
                                crop_id=crop_id,
                                panel_id=panel.panelId,
                                order_index=panel.orderIndex,
                                vector=embedding.vector,
                                quality_bucket=quality.bucket,
                                crop_kind=detection.kind,
                            )
                        )

                    crops.append(
                        CharacterCrop(
                            cropId=crop_id,
                            panelId=panel.panelId,
                            orderIndex=panel.orderIndex,
                            bbox=[x, y, w, h],
                            detectionScore=detection.detection_score,
                            kind=detection.kind,
                            detectorSource=detection.detector_source,
                            detectorModel=detection.detector_model,
                            qualityScore=quality.score,
                            qualityBucket=quality.bucket,
                            previewImage=self._build_preview_data_url(crop_image),
                            assignedClusterId=None,
                            assignmentState="unknown",
                            diagnostics={
                                **detection.diagnostics,
                                **quality.diagnostics,
                                "detectorSource": detection.detector_source,
                                "detectorModel": detection.detector_model,
                                "cropKind": detection.kind,
                                "embeddingKey": embedding.cache_key if embedding is not None else "",
                                "embeddingVersion": self.embedder.version if embedding is not None else "",
                                "embeddingDiagnostics": embedding.diagnostics if embedding is not None else {},
                            },
                        )
                    )

        raw_clusters, raw_assignments = self.clusterer.cluster(cluster_inputs)
        cluster_id_by_index = {cluster.cluster_index: f"char_{index:03d}" for index, cluster in enumerate(raw_clusters, start=1)}

        crop_by_id = {crop.cropId: crop for crop in crops}
        candidate_assignments: list[CharacterCandidateAssignment] = []
        for assignment in raw_assignments:
            crop = crop_by_id.get(assignment.crop_id)
            if crop is None:
                continue
            if assignment.cluster_index is not None:
                crop.assignedClusterId = cluster_id_by_index[assignment.cluster_index]
                crop.assignmentState = assignment.state
            for candidate in assignment.ranked_candidates:
                cluster_index = int(candidate["clusterIndex"])
                cluster_id = cluster_id_by_index.get(cluster_index)
                if cluster_id is None:
                    continue
                candidate_assignments.append(
                    CharacterCandidateAssignment(
                        cropId=crop.cropId,
                        panelId=crop.panelId,
                        clusterId=cluster_id,
                        rank=int(candidate["rank"]),
                        score=float(candidate["score"]),
                        marginScore=assignment.margin_score if int(candidate["rank"]) == 1 else 0.0,
                        state=assignment.state if int(candidate["rank"]) == 1 else "suggested",
                        diagnostics={
                            "clusterIndex": cluster_index,
                            "anchorSimilarity": candidate.get("anchorSimilarity", candidate["score"]),
                            "centroidSimilarity": candidate.get("centroidSimilarity", candidate["score"]),
                        },
                    )
                )

        clusters: list[CharacterCluster] = []
        for raw_cluster in raw_clusters:
            cluster_id = cluster_id_by_index[raw_cluster.cluster_index]
            member_crops = [
                crop_by_id[crop_id]
                for crop_id in raw_cluster.member_crop_ids
                if crop_id in crop_by_id
            ]
            anchor_crops = [
                crop_by_id[crop_id]
                for crop_id in raw_cluster.anchor_crop_ids
                if crop_id in crop_by_id
            ]
            sample_panel_ids = self._dedupe([crop.panelId for crop in member_crops])[:8]
            anchor_panel_ids = self._dedupe([crop.panelId for crop in anchor_crops])[:4]
            clusters.append(
                CharacterCluster(
                    clusterId=cluster_id,
                    chapterId=chapter_id,
                    status="review_needed",
                    displayLabel=f"nhan vat {len(clusters) + 1}",
                    confidenceScore=raw_cluster.confidence,
                    occurrenceCount=len(self._dedupe([crop.panelId for crop in member_crops])),
                    anchorCropIds=[crop.cropId for crop in anchor_crops],
                    anchorPanelIds=anchor_panel_ids,
                    samplePanelIds=sample_panel_ids,
                    reviewFlags=raw_cluster.review_flags,
                    diagnostics={
                        **raw_cluster.diagnostics,
                        "memberCropIds": [crop.cropId for crop in member_crops],
                        "memberPanelIds": sample_panel_ids,
                        "qualityBuckets": self._count_buckets(member_crops),
                    },
                )
            )

        panel_refs = self._build_panel_refs(crops=crops, clusters=clusters, candidate_assignments=candidate_assignments, panel_order=panel_order)
        unresolved_panel_ids = self._build_unresolved_panels(panels=panels, crops=crops, panel_refs=panel_refs)
        cluster_diagnostics = {
            cluster.clusterId: {
                "reviewFlags": cluster.reviewFlags,
                "confidenceScore": cluster.confidenceScore,
                "anchorCropIds": cluster.anchorCropIds,
            }
            for cluster in clusters
        }
        diagnostics = {
            "summary": {
                "panelCount": len(panels),
                "cropCount": len(crops),
                "clusterCount": len(clusters),
                "unresolvedPanelCount": len(unresolved_panel_ids),
                "versions": {
                    "prepass": PREPASS_VERSION,
                    "detector": self.detector.version,
                    "quality": self.quality_scorer.version,
                    "embedder": self.embedder.version,
                    "cluster": self.clusterer.version,
                },
                "config": {
                    "detectorMode": self.settings.character_detector_mode,
                    "device": self.settings.character_device,
                    "resolvedDevice": getattr(self.detector, "device", "cpu"),
                    "clusterer": self.settings.character_clusterer,
                    "objectModel": self.settings.character_object_model,
                    "minClusterSize": self.settings.character_min_cluster_size,
                },
                "thresholds": {
                    "anchorDistance": ANCHOR_DISTANCE_THRESHOLD,
                    "greenSimilarity": GREEN_SIMILARITY_THRESHOLD,
                    "greenMargin": GREEN_MARGIN_THRESHOLD,
                    "suggestSimilarity": SUGGEST_SIMILARITY_THRESHOLD,
                    "suggestMargin": SUGGEST_MARGIN_THRESHOLD,
                    "faceAttachSimilarity": FACE_ATTACH_SIMILARITY_THRESHOLD,
                    "faceAttachMargin": FACE_ATTACH_MARGIN_THRESHOLD,
                },
            },
            "panels": panel_diagnostics,
            "pairs": [],
        }

        return ChapterCharacterState(
            chapterId=chapter_id,
            chapterContentHash=chapter_content_hash,
            prepassVersion=PREPASS_VERSION,
            generatedAt=now,
            updatedAt=now,
            needsReview=bool(unresolved_panel_ids or any(cluster.reviewFlags for cluster in clusters)),
            clusters=clusters,
            crops=sorted(crops, key=lambda item: (item.orderIndex, item.cropId)),
            candidateAssignments=sorted(candidate_assignments, key=lambda item: (panel_order.get(item.panelId, 0), item.cropId, item.rank)),
            panelCharacterRefs=panel_refs,
            unresolvedPanelIds=unresolved_panel_ids,
            clusterDiagnostics=cluster_diagnostics,
            diagnostics=diagnostics,
        )

    def _build_panel_refs(
        self,
        *,
        crops: list[CharacterCrop],
        clusters: list[CharacterCluster],
        candidate_assignments: list[CharacterCandidateAssignment],
        panel_order: dict[str, int],
    ) -> list[PanelCharacterRef]:
        active_cluster_ids = {cluster.clusterId for cluster in clusters if cluster.status not in {"ignored", "merged"}}
        candidate_lookup: dict[tuple[str, str], CharacterCandidateAssignment] = {
            (assignment.cropId, assignment.clusterId): assignment
            for assignment in candidate_assignments
            if assignment.rank == 1
        }
        panel_refs: list[PanelCharacterRef] = []
        panel_ids = self._dedupe([crop.panelId for crop in crops] + list(panel_order.keys()))
        for panel_id in panel_ids:
            panel_crops = [crop for crop in crops if crop.panelId == panel_id]
            confirmed_cluster_ids: list[str] = []
            score_values: list[float] = []
            for crop in panel_crops:
                if crop.assignmentState not in {"auto_confirmed", "manual"} or not crop.assignedClusterId:
                    continue
                if crop.assignedClusterId not in active_cluster_ids:
                    continue
                confirmed_cluster_ids.append(crop.assignedClusterId)
                candidate = candidate_lookup.get((crop.cropId, crop.assignedClusterId))
                score_values.append(candidate.score if candidate is not None else 1.0)

            cluster_ids = self._dedupe(confirmed_cluster_ids)
            source = "auto_confirmed" if cluster_ids else "unknown"
            confidence_score = round(sum(score_values) / len(score_values), 4) if score_values else 0.0
            diagnostics = {
                "cropIds": [crop.cropId for crop in panel_crops],
                "suggestedCropIds": [
                    crop.cropId
                    for crop in panel_crops
                    if crop.assignmentState == "suggested" and crop.assignedClusterId in active_cluster_ids
                ],
            }
            panel_refs.append(
                PanelCharacterRef(
                    panelId=panel_id,
                    clusterIds=cluster_ids,
                    source=source,
                    confidenceScore=confidence_score,
                    diagnostics=diagnostics,
                )
            )
        return sorted(panel_refs, key=lambda item: panel_order.get(item.panelId, 0))

    def _build_unresolved_panels(
        self,
        *,
        panels: list[CharacterPanelReference],
        crops: list[CharacterCrop],
        panel_refs: list[PanelCharacterRef],
    ) -> list[str]:
        panel_ref_map = {ref.panelId: ref for ref in panel_refs}
        unresolved: list[str] = []
        for panel in sorted(panels, key=lambda item: item.orderIndex):
            panel_crops = [crop for crop in crops if crop.panelId == panel.panelId]
            if not panel_crops:
                unresolved.append(panel.panelId)
                continue
            if any(crop.assignmentState in {"suggested", "unknown"} for crop in panel_crops):
                unresolved.append(panel.panelId)
                continue
            ref = panel_ref_map.get(panel.panelId)
            if ref is None or not ref.clusterIds:
                unresolved.append(panel.panelId)
        return unresolved

    def _apply_manual_constraints(self, *, state: ChapterCharacterState, previous_state: ChapterCharacterState) -> None:
        active_crop_ids = {crop.cropId for crop in state.crops}
        cluster_by_id = {cluster.clusterId: cluster for cluster in state.clusters}
        previous_crops = {crop.cropId: crop for crop in previous_state.crops}
        previous_manual_refs = {
            ref.panelId: ref
            for ref in previous_state.panelCharacterRefs
            if ref.source == "manual" or ref.diagnostics.get("manualOverride")
        }

        for previous_cluster in previous_state.clusters:
            if previous_cluster.status in {"ignored", "merged"}:
                continue
            if not previous_cluster.lockName and previous_cluster.status != "locked":
                continue

            target_cluster = cluster_by_id.get(previous_cluster.clusterId)
            if target_cluster is None:
                target_cluster = CharacterCluster(
                    clusterId=self._next_cluster_id(state, preferred=previous_cluster.clusterId),
                    chapterId=state.chapterId,
                )
                state.clusters.append(target_cluster)
                cluster_by_id[target_cluster.clusterId] = target_cluster

            target_cluster.status = "locked"
            target_cluster.canonicalName = previous_cluster.canonicalName
            target_cluster.displayLabel = previous_cluster.displayLabel or previous_cluster.canonicalName
            target_cluster.lockName = True
            target_cluster.reviewFlags = [flag for flag in target_cluster.reviewFlags if flag != "possible_merge"]
            target_cluster.diagnostics = {
                **target_cluster.diagnostics,
                "manualConstraintFromClusterId": previous_cluster.clusterId,
            }

            constrained_crop_ids = [
                crop.cropId
                for crop in previous_state.crops
                if crop.assignedClusterId == previous_cluster.clusterId and crop.assignmentState == "manual" and crop.cropId in active_crop_ids
            ]
            constrained_crop_ids.extend(crop_id for crop_id in previous_cluster.anchorCropIds if crop_id in active_crop_ids)
            constrained_crop_ids = self._dedupe(constrained_crop_ids)

            for crop_id in constrained_crop_ids:
                crop = next(crop for crop in state.crops if crop.cropId == crop_id)
                crop.assignedClusterId = target_cluster.clusterId
                crop.assignmentState = "manual"
                state.candidateAssignments = [
                    assignment for assignment in state.candidateAssignments if assignment.cropId != crop.cropId
                ]
                state.candidateAssignments.append(
                    CharacterCandidateAssignment(
                        cropId=crop.cropId,
                        panelId=crop.panelId,
                        clusterId=target_cluster.clusterId,
                        rank=1,
                        score=1.0,
                        marginScore=1.0,
                        state="manual",
                        diagnostics={"manualConstraint": True},
                    )
                )

            constrained_panel_ids = [
                ref.panelId
                for ref in previous_manual_refs.values()
                if previous_cluster.clusterId in ref.clusterIds
            ]
            constrained_panel_ids.extend(previous_crops[crop_id].panelId for crop_id in constrained_crop_ids if crop_id in previous_crops)
            constrained_panel_ids = self._dedupe(constrained_panel_ids)
            for panel_id in constrained_panel_ids:
                self._upsert_panel_ref(
                    state,
                    PanelCharacterRef(
                        panelId=panel_id,
                        clusterIds=[target_cluster.clusterId],
                        source="manual",
                        confidenceScore=1.0,
                        diagnostics={"manualOverride": True, "manualConstraintFromClusterId": previous_cluster.clusterId},
                    ),
                )

        self._refresh_cluster_counts(state)
        panel_order = {crop.panelId: crop.orderIndex for crop in state.crops}
        state.panelCharacterRefs = sorted(state.panelCharacterRefs, key=lambda item: panel_order.get(item.panelId, 0))
        state.unresolvedPanelIds = self._build_unresolved_panels(
            panels=[CharacterPanelReference(panelId=panel_id, orderIndex=order_index) for panel_id, order_index in panel_order.items()],
            crops=state.crops,
            panel_refs=state.panelCharacterRefs,
        )

    def _refresh_cluster_counts(self, state: ChapterCharacterState) -> None:
        for cluster in state.clusters:
            assigned_crops = [
                crop
                for crop in state.crops
                if crop.assignedClusterId == cluster.clusterId and crop.assignmentState in {"auto_confirmed", "manual"}
            ]
            assigned_panel_ids = self._dedupe([crop.panelId for crop in assigned_crops])
            cluster.anchorCropIds = self._dedupe([*cluster.anchorCropIds, *(crop.cropId for crop in assigned_crops if crop.assignmentState == "manual")])[:6]
            cluster.anchorPanelIds = self._dedupe([*cluster.anchorPanelIds, *assigned_panel_ids])[:4]
            cluster.samplePanelIds = self._dedupe([*cluster.samplePanelIds, *assigned_panel_ids])[:8]
            cluster.occurrenceCount = len(cluster.samplePanelIds)
            if assigned_crops and cluster.confidenceScore < 1.0 and any(crop.assignmentState == "manual" for crop in assigned_crops):
                cluster.confidenceScore = 1.0

    def _upsert_panel_ref(self, state: ChapterCharacterState, next_ref: PanelCharacterRef) -> None:
        for index, ref in enumerate(state.panelCharacterRefs):
            if ref.panelId == next_ref.panelId:
                state.panelCharacterRefs[index] = next_ref
                return
        state.panelCharacterRefs.append(next_ref)

    def _next_cluster_id(self, state: ChapterCharacterState, *, preferred: str = "") -> str:
        existing = {cluster.clusterId for cluster in state.clusters}
        if preferred and preferred not in existing:
            return preferred
        index = len(existing) + 1
        while f"char_{index:03d}" in existing:
            index += 1
        return f"char_{index:03d}"

    def _build_preview_data_url(self, image: Image.Image) -> str:
        preview = image.copy()
        preview.thumbnail((112, 112))
        buffer = BytesIO()
        preview.save(buffer, format="JPEG", quality=72, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def _detector_runtime_diagnostics(self) -> dict[str, object]:
        return {
            "device": getattr(self.detector, "device", "cpu"),
            "animeProviderAvailable": not bool(getattr(self.detector, "_anime_error", "")),
            "animeProviderError": getattr(self.detector, "_anime_error", ""),
            "objectProviderAvailable": not bool(getattr(self.detector, "_object_error", "")),
            "objectProviderError": getattr(self.detector, "_object_error", ""),
        }

    def _count_buckets(self, crops: list[CharacterCrop]) -> dict[str, int]:
        counts: dict[str, int] = {"good": 0, "medium": 0, "poor": 0}
        for crop in crops:
            counts[crop.qualityBucket] = counts.get(crop.qualityBucket, 0) + 1
        return counts

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _is_reusable_state(
        self,
        state: ChapterCharacterState | None,
        *,
        chapter_content_hash: str,
    ) -> bool:
        if state is None:
            return False
        if state.chapterContentHash != chapter_content_hash:
            return False
        if state.prepassVersion != PREPASS_VERSION:
            return False
        if not state.crops:
            return False
        return True

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
