from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import cv2
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

PREPASS_VERSION = "character-dedup-v6"

IDENTITY_KINDS = {"face", "head"}
MIN_FACE_SIZE = 48
MIN_HEAD_SIZE = 64
MIN_FACE_QUALITY = 0.58
MIN_HEAD_QUALITY = 0.62
MIN_DETECTOR_CONFIDENCE = 0.45
MIN_LEARNED_FACE_QUALITY = 0.50
MIN_LEARNED_HEAD_QUALITY = 0.52
MIN_STRONG_FACE_DETECTION = 0.70
MIN_STRONG_HEAD_DETECTION = 0.68
MIN_ANIME_IDENTITY_DETECTION = 0.64
MIN_FALLBACK_HEURISTIC_QUALITY = 0.48
MIN_FALLBACK_HEURISTIC_DETECTION = 0.38
MIN_FALLBACK_HEURISTIC_SATURATION = 0.10
DUPLICATE_CONTAINMENT_THRESHOLD = 0.90


class CharacterPrepassService:
    def __init__(self, settings: Settings, repository: CharacterStateRepository) -> None:
        self.settings = settings
        self.repository = repository
        self.detector = CharacterCropDetector(settings)
        self.quality_scorer = CharacterCropQualityScorer()
        self.embedder = CharacterCropEmbedder(
            settings.character_cache_root,
            embedder=settings.character_embedder,
            dino_model_path=settings.character_dino_model_resolved_path,
            arcface_model_path=settings.character_arcface_model_resolved_path,
            embed_device=settings.character_embed_device,
        )
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

        self.embedder.validate_runtime()
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
        pending_embeddings: list[dict[str, object]] = []
        panel_diagnostics: dict[str, object] = {}
        metrics = {
            "totalDetectedCrops": 0,
            "suppressedDuplicateCrops": 0,
            "identityEligibleCrops": 0,
            "rejectedLowQualityCrops": 0,
            "rejectedKindCrops": 0,
            "rejectedMonsterCrops": 0,
            "unknownCrops": 0,
        }

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
                    "detectorMix": "hybrid mode keeps anime-face-detector crops and OpenCV heuristic fallback crops in the same review surface.",
                }
                metrics["totalDetectedCrops"] += len(detections)
                detection_records: list[dict[str, object]] = []
                for detection_index, detection in enumerate(detections, start=1):
                    x, y, w, h = detection.bbox
                    crop_image = panel_image.crop((x, y, x + w, y + h))
                    crop_kind = detection.kind
                    monster_like = self._is_monster_like_crop(panel_rgb=panel_rgb, bbox=detection.bbox)
                    if monster_like:
                        crop_kind = "monster"
                    quality = self.quality_scorer.score(
                        panel_rgb=panel_rgb,
                        bbox=detection.bbox,
                        detection_score=detection.detection_score,
                    )
                    detection_records.append(
                        {
                            "crop_id": f"{panel.panelId}::crop::{detection_index:02d}",
                            "detection": detection,
                            "crop_kind": crop_kind,
                            "monster_like": monster_like,
                            "quality": quality,
                            "crop_image": crop_image,
                            "suppressed_by_crop_id": "",
                            "suppression_reason": "",
                            "duplicate_group_id": "",
                        }
                    )
                self._suppress_duplicate_records(detection_records)
                suppressed_count = sum(1 for record in detection_records if record.get("suppressed_by_crop_id"))
                metrics["suppressedDuplicateCrops"] += suppressed_count
                panel_diagnostics[panel.panelId] = {
                    **panel_diagnostics[panel.panelId],
                    "suppressedDuplicateCropCount": suppressed_count,
                }

                panel_has_reliable_identity = any(
                    self._face_head_identity_gate(
                        crop_kind=str(record["crop_kind"]),
                        bbox=record["detection"].bbox,  # type: ignore[union-attr]
                        quality_score=record["quality"].score,  # type: ignore[union-attr]
                        detection_score=record["detection"].detection_score,  # type: ignore[union-attr]
                    )[0]
                    and not record.get("suppressed_by_crop_id")
                    for record in detection_records
                )

                for record in detection_records:
                    detection = record["detection"]  # type: ignore[assignment]
                    quality = record["quality"]  # type: ignore[assignment]
                    crop_kind = str(record["crop_kind"])
                    crop_image = record["crop_image"]  # type: ignore[assignment]
                    monster_like = bool(record["monster_like"])
                    crop_id = str(record["crop_id"])
                    x, y, w, h = detection.bbox
                    identity_eligible, rejection_reason = self._identity_gate(
                        crop_kind=crop_kind,
                        bbox=detection.bbox,
                        quality_score=quality.score,
                        detection_score=detection.detection_score,
                        quality_bucket=quality.bucket,
                        panel_has_reliable_identity=panel_has_reliable_identity,
                    )
                    if record.get("suppressed_by_crop_id"):
                        identity_eligible = False
                        rejection_reason = "duplicate_suppressed"
                    if (
                        identity_eligible
                        and crop_kind == "heuristic"
                        and float(quality.diagnostics.get("saturation", 0.0)) < MIN_FALLBACK_HEURISTIC_SATURATION
                    ):
                        identity_eligible = False
                        rejection_reason = "low_color_identity_signal"
                    identity_role = "fallback_head" if identity_eligible and crop_kind == "heuristic" else "identity"
                    if identity_eligible:
                        metrics["identityEligibleCrops"] += 1
                    elif crop_kind == "monster":
                        metrics["rejectedMonsterCrops"] += 1
                    elif crop_kind not in IDENTITY_KINDS:
                        metrics["rejectedKindCrops"] += 1
                    elif rejection_reason in {"quality", "size", "detector_confidence"}:
                        metrics["rejectedLowQualityCrops"] += 1
                    metrics["unknownCrops"] += 0 if identity_eligible else 1
                    cache_hint = ":".join(
                        [
                            self.detector.version,
                            detection.detector_source,
                            detection.detector_model,
                            crop_kind,
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
                            identity_role,
                        ]
                    )
                    if identity_eligible:
                        pending_embeddings.append(
                            {
                                "crop_id": crop_id,
                                "panel_id": panel.panelId,
                                "order_index": panel.orderIndex,
                                "crop_kind": crop_kind,
                                "identity_role": identity_role,
                                "quality_bucket": quality.bucket,
                                "crop_image": crop_image.copy(),
                                "cache_hint": cache_hint,
                            }
                        )

                    crops.append(
                        CharacterCrop(
                            cropId=crop_id,
                            panelId=panel.panelId,
                            orderIndex=panel.orderIndex,
                            bbox=[x, y, w, h],
                            detectionScore=detection.detection_score,
                            kind=crop_kind,
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
                                "cropKind": crop_kind,
                                "identityRole": identity_role,
                                "identityEligible": identity_eligible,
                                "identityGateReason": rejection_reason,
                                "identityRejectionReason": rejection_reason,
                                "suppressedByCropId": record.get("suppressed_by_crop_id", ""),
                                "suppressionReason": record.get("suppression_reason", ""),
                                "duplicateGroupId": record.get("duplicate_group_id", ""),
                                "monsterLike": monster_like,
                                "panelHasReliableIdentity": panel_has_reliable_identity,
                                "embeddingProvider": "",
                                "embeddingKey": "",
                                "embeddingVersion": "",
                                "embeddingDiagnostics": {},
                            },
                        )
                    )

        crop_by_id = {crop.cropId: crop for crop in crops}
        embeddings = self.embedder.embed_batch(chapter_id=chapter_id, items=pending_embeddings)
        for item, embedding in zip(pending_embeddings, embeddings, strict=False):
            crop_id = str(item["crop_id"])
            crop = crop_by_id.get(crop_id)
            if crop is None:
                continue
            crop.diagnostics = {
                **crop.diagnostics,
                "embeddingKey": embedding.cache_key,
                "embeddingVersion": self.embedder.version,
                "embeddingProvider": embedding.diagnostics.get("provider", "handcrafted"),
                "embeddingDiagnostics": embedding.diagnostics,
            }
            embedding_provider = str(embedding.diagnostics.get("provider", "handcrafted"))
            if self.embedder.learned_mode and embedding_provider == "handcrafted":
                crop.diagnostics = {
                    **crop.diagnostics,
                    "learnedFallbackReason": "Handcrafted embedding was produced in learned mode, so this crop is excluded from automatic identity clustering.",
                }
                continue
            cluster_inputs.append(
                ClusterInputCrop(
                    crop_id=crop_id,
                    panel_id=str(item["panel_id"]),
                    order_index=int(item["order_index"]),
                    vector=embedding.vector,
                    quality_bucket=str(item["quality_bucket"]),
                    crop_kind=str(item["crop_kind"]),
                    embedding_provider=embedding_provider,
                    identity_role=str(item.get("identity_role", "identity")),
                    learned_mode=self.embedder.learned_mode,
                )
            )

        raw_clusters, raw_assignments = self.clusterer.cluster(cluster_inputs)
        cluster_id_by_index = {cluster.cluster_index: f"char_{index:03d}" for index, cluster in enumerate(raw_clusters, start=1)}
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
                    "embedder": self.settings.character_embedder,
                    "dinoModelPath": self.settings.character_dino_model_path,
                    "arcfaceModelPath": self.settings.character_arcface_model_path,
                    "embedDevice": self.settings.character_embed_device,
                    "animeFaceModelPath": getattr(self.settings, "character_anime_face_model_path", ""),
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
                "characterMetrics": {
                    **metrics,
                    "confirmedClusters": len(clusters),
                    "candidateClusters": len([cluster for cluster in clusters if cluster.status == "review_needed"]),
                    "impureClustersAfterClean": len(
                        [cluster for cluster in clusters if "impure_cluster" in cluster.reviewFlags or "outliers_rejected" in cluster.reviewFlags]
                    ),
                },
                "embedderRuntime": self.embedder.runtime_diagnostics(),
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

    def _suppress_duplicate_records(self, records: list[dict[str, object]]) -> None:
        ordered = sorted(records, key=self._duplicate_priority, reverse=True)
        duplicate_index = 1
        for canonical in ordered:
            if canonical.get("suppressed_by_crop_id"):
                continue
            suppressed_any = False
            for candidate in ordered:
                if candidate is canonical or candidate.get("suppressed_by_crop_id"):
                    continue
                if not self._is_duplicate_record_pair(canonical, candidate):
                    continue
                group_id = str(canonical.get("duplicate_group_id") or f"{canonical['crop_id']}::dup::{duplicate_index:02d}")
                if not canonical.get("duplicate_group_id"):
                    canonical["duplicate_group_id"] = group_id
                    duplicate_index += 1
                candidate["suppressed_by_crop_id"] = str(canonical["crop_id"])
                candidate["suppression_reason"] = self._duplicate_suppression_reason(canonical, candidate)
                candidate["duplicate_group_id"] = group_id
                suppressed_any = True
            if suppressed_any and not canonical.get("duplicate_group_id"):
                canonical["duplicate_group_id"] = f"{canonical['crop_id']}::dup::{duplicate_index:02d}"
                duplicate_index += 1

    def _is_duplicate_record_pair(self, left: dict[str, object], right: dict[str, object]) -> bool:
        left_detection = left["detection"]
        right_detection = right["detection"]
        left_bbox = left_detection.bbox  # type: ignore[attr-defined]
        right_bbox = right_detection.bbox  # type: ignore[attr-defined]
        containment = self._containment_ratio(left_bbox, right_bbox)
        if containment < DUPLICATE_CONTAINMENT_THRESHOLD:
            return False
        left_kind = str(left["crop_kind"])
        right_kind = str(right["crop_kind"])
        if "heuristic" in {left_kind, right_kind}:
            return True
        if {left_kind, right_kind}.issubset({"face", "head"}):
            return True
        return self._center_distance_ratio(left_bbox, right_bbox) <= 0.45

    def _duplicate_priority(self, record: dict[str, object]) -> tuple[int, float, float]:
        detection = record["detection"]
        quality = record["quality"]
        crop_kind = str(record["crop_kind"])
        detector_source = str(getattr(detection, "detector_source", ""))
        kind_priority = {
            "face": 50,
            "head": 35,
            "upper_body": 15,
            "person": 12,
            "heuristic": 5,
        }.get(crop_kind, 0)
        source_priority = 40 if detector_source == "anime-face-detector" else 10 if detector_source == "opencv-heuristic" else 20
        return (
            source_priority + kind_priority,
            float(getattr(quality, "score", 0.0)),
            float(getattr(detection, "detection_score", 0.0)),
        )

    def _duplicate_suppression_reason(self, canonical: dict[str, object], candidate: dict[str, object]) -> str:
        canonical_kind = str(canonical["crop_kind"])
        candidate_kind = str(candidate["crop_kind"])
        if canonical_kind == "face" and candidate_kind == "head":
            return "face_inside_head"
        if candidate_kind == "heuristic":
            return "anime_or_identity_crop_over_heuristic"
        return "contained_duplicate"

    def _containment_ratio(self, left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
        intersection = self._intersection_area(left, right)
        smaller = min(left[2] * left[3], right[2] * right[3])
        return 0.0 if smaller <= 0 else intersection / float(smaller)

    def _center_distance_ratio(self, left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
        left_cx = left[0] + (left[2] / 2.0)
        left_cy = left[1] + (left[3] / 2.0)
        right_cx = right[0] + (right[2] / 2.0)
        right_cy = right[1] + (right[3] / 2.0)
        dx = left_cx - right_cx
        dy = left_cy - right_cy
        larger_diagonal = max(
            (left[2] ** 2 + left[3] ** 2) ** 0.5,
            (right[2] ** 2 + right[3] ** 2) ** 0.5,
            1.0,
        )
        return ((dx * dx + dy * dy) ** 0.5) / larger_diagonal

    def _intersection_area(self, left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> int:
        left_x, left_y, left_w, left_h = left
        right_x, right_y, right_w, right_h = right
        x1 = max(left_x, right_x)
        y1 = max(left_y, right_y)
        x2 = min(left_x + left_w, right_x + right_w)
        y2 = min(left_y + left_h, right_y + right_h)
        return max(0, x2 - x1) * max(0, y2 - y1)

    def _build_panel_refs(
        self,
        *,
        crops: list[CharacterCrop],
        clusters: list[CharacterCluster],
        candidate_assignments: list[CharacterCandidateAssignment],
        panel_order: dict[str, int],
    ) -> list[PanelCharacterRef]:
        active_cluster_ids = {cluster.clusterId for cluster in clusters if cluster.status not in {"ignored", "merged"}}
        cluster_by_id = {cluster.clusterId: cluster for cluster in clusters}
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
                cluster = cluster_by_id.get(crop.assignedClusterId)
                if crop.assignmentState != "manual" and cluster is not None:
                    review_flags = set(cluster.reviewFlags)
                    if "impure_cluster" in review_flags or "low_confidence" in review_flags:
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
            ref = panel_ref_map.get(panel.panelId)
            if ref is not None and ref.diagnostics.get("manualOverride") and ref.clusterIds:
                continue
            panel_crops = [crop for crop in crops if crop.panelId == panel.panelId]
            if not panel_crops:
                unresolved.append(panel.panelId)
                continue
            identity_crops = [crop for crop in panel_crops if self._is_identity_relevant_crop(crop)]
            if any(crop.assignmentState in {"suggested", "unknown"} for crop in identity_crops):
                unresolved.append(panel.panelId)
                continue
            if identity_crops and (ref is None or not ref.clusterIds):
                unresolved.append(panel.panelId)
        return unresolved

    def _is_identity_relevant_crop(self, crop: CharacterCrop) -> bool:
        if crop.diagnostics.get("suppressedByCropId"):
            return False
        if crop.kind in IDENTITY_KINDS:
            return True
        diagnostics = crop.diagnostics or {}
        return bool(diagnostics.get("identityEligible") or diagnostics.get("identityRole") == "fallback_head")

    def _apply_manual_constraints(self, *, state: ChapterCharacterState, previous_state: ChapterCharacterState) -> None:
        active_crop_ids = {crop.cropId for crop in state.crops}
        cluster_by_id = {cluster.clusterId: cluster for cluster in state.clusters}
        previous_crops = {crop.cropId: crop for crop in previous_state.crops}
        previous_manual_refs = {
            ref.panelId: ref
            for ref in previous_state.panelCharacterRefs
            if ref.source == "manual" or ref.diagnostics.get("manualOverride")
        }

        # Phase 3: Collect split constraints to prevent re-merge
        split_constraints: dict[str, set[str]] = {}  # split_cluster_id -> {source_cluster_id}
        for previous_cluster in previous_state.clusters:
            split_from = previous_cluster.diagnostics.get("splitFromClusterId")
            if split_from and isinstance(split_from, str):
                split_constraints.setdefault(previous_cluster.clusterId, set()).add(split_from)
                split_constraints.setdefault(split_from, set()).add(previous_cluster.clusterId)

        # Phase 3: Build anchor bank from locked/manual clusters (prefer face/head vectors)
        anchor_bank: dict[str, list[np.ndarray]] = {}  # cluster_id -> list of vectors
        for previous_cluster in previous_state.clusters:
            if previous_cluster.status in {"ignored", "merged"}:
                continue
            if not previous_cluster.lockName and previous_cluster.status != "locked":
                continue
            anchor_vectors: list[np.ndarray] = []
            for crop_id in previous_cluster.anchorCropIds:
                prev_crop = previous_crops.get(crop_id)
                if prev_crop is None:
                    continue
                if prev_crop.kind not in IDENTITY_KINDS:
                    continue
                embedding_key = prev_crop.diagnostics.get("embeddingKey", "")
                if not embedding_key:
                    continue
                # Try to load cached vector
                import hashlib as _hashlib
                cache_dir = self.settings.character_cache_root / _hashlib.sha1(state.chapterId.encode("utf-8")).hexdigest()[:12] / "embeddings"
                vector_path = cache_dir / f"{embedding_key}.npy"
                if vector_path.exists():
                    try:
                        vector = np.load(vector_path)
                        anchor_vectors.append(vector)
                    except Exception:
                        pass
            if anchor_vectors:
                anchor_bank[previous_cluster.clusterId] = anchor_vectors

        # Restore locked clusters (existing behavior)
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

        # Phase 3: Anchor bank propagation - match unassigned face/head crops against locked anchors
        ANCHOR_PROPAGATE_THRESHOLD = 0.88
        ANCHOR_PROPAGATE_MARGIN = 0.10
        locked_cluster_ids = {c.clusterId for c in state.clusters if c.lockName and c.status == "locked"}

        if anchor_bank:
            for crop in state.crops:
                if crop.assignmentState in {"manual", "auto_confirmed"}:
                    continue
                if crop.kind not in {"face", "head"}:
                    continue
                embedding_key = crop.diagnostics.get("embeddingKey", "")
                if not embedding_key:
                    continue
                import hashlib as _hashlib
                cache_dir = self.settings.character_cache_root / _hashlib.sha1(state.chapterId.encode("utf-8")).hexdigest()[:12] / "embeddings"
                vector_path = cache_dir / f"{embedding_key}.npy"
                if not vector_path.exists():
                    continue
                try:
                    crop_vector = np.load(vector_path)
                except Exception:
                    continue

                # Score against all anchor banks
                scored: list[tuple[str, float]] = []
                for anchor_cluster_id, anchor_vectors in anchor_bank.items():
                    if anchor_cluster_id not in locked_cluster_ids:
                        continue
                    anchor_matrix = np.stack(anchor_vectors, axis=0)
                    similarities = anchor_matrix @ crop_vector
                    best_sim = float(np.max(similarities))
                    centroid = anchor_matrix.mean(axis=0)
                    norm = float(np.linalg.norm(centroid))
                    if norm > 1e-6:
                        centroid = centroid / norm
                    centroid_sim = float(np.dot(crop_vector, centroid))
                    combined = centroid_sim * 0.55 + best_sim * 0.45
                    scored.append((anchor_cluster_id, combined))

                if not scored:
                    continue
                scored.sort(key=lambda x: x[1], reverse=True)
                best_cluster_id, best_score = scored[0]
                second_score = scored[1][1] if len(scored) > 1 else 0.0
                margin = best_score - second_score

                # Check split constraints - don't merge into a cluster that was split from this one
                blocked_by_split = False
                if best_cluster_id in split_constraints:
                    current_assigned = crop.assignedClusterId
                    if current_assigned and current_assigned in split_constraints[best_cluster_id]:
                        blocked_by_split = True

                # Check anchor conflict
                if len(scored) > 1 and margin < ANCHOR_PROPAGATE_MARGIN and scored[1][1] >= ANCHOR_PROPAGATE_THRESHOLD:
                    # Conflict between two locked anchors
                    crop.assignmentState = "suggested"
                    crop.assignedClusterId = best_cluster_id
                    crop.diagnostics = {
                        **crop.diagnostics,
                        "anchorConflict": True,
                        "anchorCandidates": [{"clusterId": cid, "score": round(s, 4)} for cid, s in scored[:3]],
                    }
                    # Add review flag to the cluster
                    target = cluster_by_id.get(best_cluster_id)
                    if target and "anchor_conflict" not in target.reviewFlags:
                        target.reviewFlags.append("anchor_conflict")
                elif best_score >= ANCHOR_PROPAGATE_THRESHOLD and margin >= ANCHOR_PROPAGATE_MARGIN and not blocked_by_split:
                    # Strong match with clear margin - auto-confirm via anchor propagation
                    crop.assignedClusterId = best_cluster_id
                    crop.assignmentState = "auto_confirmed"
                    crop.diagnostics = {
                        **crop.diagnostics,
                        "anchorPropagation": True,
                        "anchorScore": round(best_score, 4),
                        "anchorMargin": round(margin, 4),
                    }
                    state.candidateAssignments = [
                        a for a in state.candidateAssignments if a.cropId != crop.cropId
                    ]
                    state.candidateAssignments.append(
                        CharacterCandidateAssignment(
                            cropId=crop.cropId,
                            panelId=crop.panelId,
                            clusterId=best_cluster_id,
                            rank=1,
                            score=round(best_score, 4),
                            marginScore=round(margin, 4),
                            state="auto_confirmed",
                            diagnostics={"anchorPropagation": True},
                        )
                    )
                    # Update panel ref for this propagated crop
                    self._upsert_panel_ref(
                        state,
                        PanelCharacterRef(
                            panelId=crop.panelId,
                            clusterIds=[best_cluster_id],
                            source="auto_confirmed",
                            confidenceScore=round(best_score, 4),
                            diagnostics={"anchorPropagation": True},
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
        return self.detector.runtime_diagnostics()

    def _identity_gate(
        self,
        *,
        crop_kind: str,
        bbox: tuple[int, int, int, int],
        quality_score: float,
        detection_score: float,
        quality_bucket: str = "poor",
        panel_has_reliable_identity: bool = False,
    ) -> tuple[bool, str]:
        if crop_kind == "heuristic" and self.embedder.learned_mode:
            if panel_has_reliable_identity:
                return False, "context_fallback_not_needed"
            if quality_bucket not in {"good", "medium"}:
                return False, "quality"
            if quality_score < MIN_FALLBACK_HEURISTIC_QUALITY:
                return False, "quality"
            if detection_score < MIN_FALLBACK_HEURISTIC_DETECTION:
                return False, "detector_confidence"
            return True, ""
        return self._face_head_identity_gate(
            crop_kind=crop_kind,
            bbox=bbox,
            quality_score=quality_score,
            detection_score=detection_score,
        )

    def _face_head_identity_gate(
        self,
        *,
        crop_kind: str,
        bbox: tuple[int, int, int, int],
        quality_score: float,
        detection_score: float,
    ) -> tuple[bool, str]:
        if crop_kind not in IDENTITY_KINDS:
            return False, "kind"
        _x, _y, width, height = bbox
        min_size = MIN_FACE_SIZE if crop_kind == "face" else MIN_HEAD_SIZE
        if width < min_size or height < min_size:
            return False, "size"
        if detection_score < MIN_DETECTOR_CONFIDENCE:
            return False, "detector_confidence"
        if self.embedder.learned_mode:
            if crop_kind == "face" and detection_score >= MIN_STRONG_FACE_DETECTION and quality_score >= MIN_LEARNED_FACE_QUALITY:
                return True, ""
            if crop_kind == "head" and detection_score >= MIN_STRONG_HEAD_DETECTION and quality_score >= MIN_LEARNED_HEAD_QUALITY:
                return True, ""
            return False, "weak_anime_face"
        min_quality = MIN_FACE_QUALITY if crop_kind == "face" else MIN_HEAD_QUALITY
        if quality_score < min_quality:
            return False, "quality"
        return True, ""

    def _is_monster_like_crop(self, *, panel_rgb: np.ndarray, bbox: tuple[int, int, int, int]) -> bool:
        x, y, width, height = bbox
        crop = panel_rgb[y : y + height, x : x + width]
        if crop.size == 0:
            return False
        hsv = np.asarray(Image.fromarray(crop).convert("HSV"), dtype=np.uint8)
        hue = hsv[:, :, 0].astype(np.float32) * 2.0
        saturation = hsv[:, :, 1].astype(np.float32) / 255.0
        value = hsv[:, :, 2].astype(np.float32) / 255.0
        green_mask = (hue >= 70.0) & (hue <= 170.0) & (saturation > 0.28) & (value > 0.18)
        skin_like_mask = (hue >= 8.0) & (hue <= 52.0) & (saturation > 0.10) & (saturation < 0.62) & (value > 0.32)
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        edge_density = float(np.mean(cv2.Canny(gray, 70, 170) > 0))
        green_ratio = float(np.mean(green_mask))
        skin_like_ratio = float(np.mean(skin_like_mask))
        aspect_ratio = width / max(1.0, float(height))
        long_shape = aspect_ratio > 1.85 or aspect_ratio < 0.20
        return bool((green_ratio > 0.42 and skin_like_ratio < 0.18) or (edge_density > 0.38 and long_shape))

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
        summary = state.diagnostics.get("summary") if isinstance(state.diagnostics, dict) else {}
        if not isinstance(summary, dict):
            return False
        versions = summary.get("versions") if isinstance(summary.get("versions"), dict) else {}
        config = summary.get("config") if isinstance(summary.get("config"), dict) else {}

        expected_versions = {
            "prepass": PREPASS_VERSION,
            "detector": self.detector.version,
            "quality": self.quality_scorer.version,
            "embedder": self.embedder.version,
            "cluster": self.clusterer.version,
        }
        for key, expected_value in expected_versions.items():
            if versions.get(key) != expected_value:
                return False

        expected_config = {
            "detectorMode": self.settings.character_detector_mode,
            "clusterer": self.settings.character_clusterer,
            "minClusterSize": self.settings.character_min_cluster_size,
            "objectModel": self.settings.character_object_model,
            "device": self.settings.character_device,
            "embedder": self.settings.character_embedder,
            "dinoModelPath": self.settings.character_dino_model_path,
            "arcfaceModelPath": self.settings.character_arcface_model_path,
            "embedDevice": self.settings.character_embed_device,
            "animeFaceModelPath": getattr(self.settings, "character_anime_face_model_path", ""),
        }
        for key, expected_value in expected_config.items():
            if config.get(key) != expected_value:
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
