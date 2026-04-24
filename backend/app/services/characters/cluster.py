from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.cluster import AgglomerativeClustering, HDBSCAN


CLUSTER_VERSION = "hybrid-hdbscan-v4"
GREEN_SIMILARITY_THRESHOLD = 0.90
GREEN_MARGIN_THRESHOLD = 0.12
SUGGEST_SIMILARITY_THRESHOLD = 0.76
SUGGEST_MARGIN_THRESHOLD = 0.05
ANCHOR_DISTANCE_THRESHOLD = 0.06
FACE_ATTACH_SIMILARITY_THRESHOLD = 0.94
FACE_ATTACH_MARGIN_THRESHOLD = 0.12

IDENTITY_STRONG_KINDS = {"face", "head"}
IDENTITY_USABLE_KINDS = {"face", "head", "heuristic"}
CONTEXT_ONLY_KINDS = {"person", "upper_body", "accessory"}


@dataclass(frozen=True)
class ClusterInputCrop:
    crop_id: str
    panel_id: str
    order_index: int
    vector: np.ndarray
    quality_bucket: str
    crop_kind: str = "heuristic"


@dataclass(frozen=True)
class ClusterAssignmentResult:
    crop_id: str
    cluster_index: int | None
    state: str
    score: float
    margin_score: float
    ranked_candidates: list[dict[str, float | int | str]]


@dataclass(frozen=True)
class ClusterSummary:
    cluster_index: int
    anchor_crop_ids: list[str]
    member_crop_ids: list[str]
    confidence: float
    review_flags: list[str]
    diagnostics: dict[str, object]


class CharacterClusterer:
    def __init__(self, *, clusterer: str = "hdbscan", min_cluster_size: int = 2) -> None:
        self.clusterer = clusterer
        self.min_cluster_size = max(2, min_cluster_size)
        self.version = CLUSTER_VERSION

    def cluster(self, crops: list[ClusterInputCrop]) -> tuple[list[ClusterSummary], list[ClusterAssignmentResult]]:
        if not crops:
            return [], []

        anchors = [crop for crop in crops if crop.quality_bucket == "good" and crop.crop_kind in IDENTITY_USABLE_KINDS]
        anchors = anchors or [crop for crop in crops if crop.quality_bucket == "medium" and crop.crop_kind in IDENTITY_USABLE_KINDS]
        if not anchors:
            return [], [self._unknown_assignment(crop) for crop in crops]

        labels = self._cluster_anchor_labels(anchors)
        anchor_groups: dict[int, list[ClusterInputCrop]] = {}
        noise_crop_ids: list[str] = []
        for label, crop in zip(labels.tolist(), anchors, strict=True):
            if label < 0:
                noise_crop_ids.append(crop.crop_id)
                continue
            anchor_groups.setdefault(int(label), []).append(crop)

        if not anchor_groups:
            return [], [self._unknown_assignment(crop) for crop in crops]

        clusters, cluster_anchor_crops, cluster_anchor_vectors = self._build_clusters(anchor_groups, noise_crop_ids=noise_crop_ids)
        assignments = self._assign_crops(crops=crops, clusters=clusters, cluster_anchor_crops=cluster_anchor_crops)
        normalized_clusters = self._normalize_cluster_members(
            clusters=clusters,
            assignments=assignments,
            cluster_anchor_vectors=cluster_anchor_vectors,
        )
        return normalized_clusters, assignments

    def _cluster_anchor_labels(self, anchors: list[ClusterInputCrop]) -> np.ndarray:
        if len(anchors) < self.min_cluster_size:
            return np.full((len(anchors),), -1, dtype=np.int32)

        vectors = np.stack([crop.vector for crop in anchors], axis=0)
        distances = self._cosine_distance_matrix(vectors=vectors, crops=anchors)
        if self.clusterer == "agglomerative":
            return self._cluster_with_agglomerative(distances)

        try:
            hdbscan = HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                min_samples=1,
                metric="precomputed",
                cluster_selection_method="leaf",
                cluster_selection_epsilon=ANCHOR_DISTANCE_THRESHOLD,
                allow_single_cluster=True,
            )
            labels = hdbscan.fit_predict(distances)
        except Exception:
            labels = self._cluster_with_agglomerative(distances)
        if not np.any(labels >= 0) and self._has_close_pair(distances):
            labels = self._cluster_with_agglomerative(distances)
        return self._mark_small_groups_as_noise(labels)

    def _cluster_with_agglomerative(self, distances: np.ndarray) -> np.ndarray:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            metric="precomputed",
            linkage="complete",
            distance_threshold=ANCHOR_DISTANCE_THRESHOLD,
        )
        return clustering.fit_predict(distances)

    def _has_close_pair(self, distances: np.ndarray) -> bool:
        if distances.shape[0] < 2:
            return False
        upper = distances[np.triu_indices(distances.shape[0], k=1)]
        finite = upper[np.isfinite(upper)]
        return bool(finite.size and float(np.min(finite)) <= ANCHOR_DISTANCE_THRESHOLD)

    def _mark_small_groups_as_noise(self, labels: np.ndarray) -> np.ndarray:
        normalized = labels.astype(np.int32, copy=True)
        for label in set(int(value) for value in normalized.tolist() if value >= 0):
            if int(np.sum(normalized == label)) < self.min_cluster_size:
                normalized[normalized == label] = -1
        return normalized

    def _build_clusters(
        self,
        anchor_groups: dict[int, list[ClusterInputCrop]],
        *,
        noise_crop_ids: list[str],
    ) -> tuple[list[ClusterSummary], dict[int, list[ClusterInputCrop]], dict[int, np.ndarray]]:
        clusters: list[ClusterSummary] = []
        ordered_labels = sorted(anchor_groups.keys(), key=lambda label: min(item.order_index for item in anchor_groups[label]))
        label_to_cluster_index = {label: index for index, label in enumerate(ordered_labels)}
        cluster_anchor_vectors: dict[int, np.ndarray] = {}
        cluster_anchor_crops: dict[int, list[ClusterInputCrop]] = {}

        for label in ordered_labels:
            cluster_index = label_to_cluster_index[label]
            items = sorted(anchor_groups[label], key=lambda item: item.order_index)
            cluster_anchor_vectors[cluster_index] = np.stack([item.vector for item in items], axis=0)
            cluster_anchor_crops[cluster_index] = items
            confidence = self._cluster_confidence(cluster_anchor_vectors[cluster_index])
            kinds = sorted({item.crop_kind for item in items})
            review_flags = ["review_needed", "hdbscan"]
            if not any(kind in IDENTITY_STRONG_KINDS for kind in kinds):
                review_flags.append("weak_identity_signal")
            clusters.append(
                ClusterSummary(
                    cluster_index=cluster_index,
                    anchor_crop_ids=[item.crop_id for item in items],
                    member_crop_ids=[item.crop_id for item in items],
                    confidence=confidence,
                    review_flags=review_flags,
                    diagnostics={
                        "anchorCount": len(items),
                        "anchorCropIds": [item.crop_id for item in items],
                        "anchorKinds": kinds,
                        "noiseCropIds": noise_crop_ids,
                        "clusterer": self.clusterer,
                        "minClusterSize": self.min_cluster_size,
                    },
                )
            )
        return clusters, cluster_anchor_crops, cluster_anchor_vectors

    def _assign_crops(
        self,
        *,
        crops: list[ClusterInputCrop],
        clusters: list[ClusterSummary],
        cluster_anchor_crops: dict[int, list[ClusterInputCrop]],
    ) -> list[ClusterAssignmentResult]:
        assignments: list[ClusterAssignmentResult] = []
        anchor_to_cluster_index = {
            crop.crop_id: cluster_index
            for cluster_index, cluster_crops in cluster_anchor_crops.items()
            for crop in cluster_crops
        }
        cluster_by_index = {cluster.cluster_index: cluster for cluster in clusters}

        for crop in crops:
            if crop.crop_id in anchor_to_cluster_index:
                cluster_index = anchor_to_cluster_index[crop.crop_id]
                state = self._anchor_assignment_state(crop, cluster_by_index[cluster_index])
                assignments.append(
                    ClusterAssignmentResult(
                        crop_id=crop.crop_id,
                        cluster_index=cluster_index,
                        state=state,
                        score=1.0,
                        margin_score=1.0,
                        ranked_candidates=[{"clusterIndex": cluster_index, "score": 1.0, "marginScore": 1.0, "rank": 1}],
                    )
                )
                continue

            ranked_candidates = self._rank_candidates(crop=crop, clusters=clusters, cluster_anchor_crops=cluster_anchor_crops)
            best = ranked_candidates[0] if ranked_candidates else None
            second = ranked_candidates[1] if len(ranked_candidates) > 1 else None
            top_score = float(best["score"]) if best is not None else 0.0
            margin_score = top_score - (float(second["score"]) if second is not None else 0.0)

            if best is not None and self._can_attach_auto(crop=crop, top_score=top_score, margin_score=margin_score):
                state = "auto_confirmed"
                cluster_index = int(best["clusterIndex"])
            elif best is not None and top_score >= SUGGEST_SIMILARITY_THRESHOLD and margin_score >= SUGGEST_MARGIN_THRESHOLD:
                state = "suggested"
                cluster_index = int(best["clusterIndex"])
            else:
                state = "unknown"
                cluster_index = None

            assignments.append(
                ClusterAssignmentResult(
                    crop_id=crop.crop_id,
                    cluster_index=cluster_index,
                    state=state,
                    score=round(top_score, 4),
                    margin_score=round(margin_score, 4),
                    ranked_candidates=ranked_candidates[:3],
                )
            )
        return assignments

    def _rank_candidates(
        self,
        *,
        crop: ClusterInputCrop,
        clusters: list[ClusterSummary],
        cluster_anchor_crops: dict[int, list[ClusterInputCrop]],
    ) -> list[dict[str, float | int | str]]:
        if crop.crop_kind in CONTEXT_ONLY_KINDS:
            return []
        ranked_candidates: list[dict[str, float | int | str]] = []
        for cluster in clusters:
            anchor_crops = cluster_anchor_crops[cluster.cluster_index]
            if any(anchor_crop.panel_id == crop.panel_id for anchor_crop in anchor_crops):
                continue
            score, centroid_similarity, strongest_anchor_similarity = self._score_against_cluster(
                crop=crop,
                cluster_crops=anchor_crops,
            )
            ranked_candidates.append(
                {
                    "clusterIndex": cluster.cluster_index,
                    "score": round(score, 4),
                    "anchorSimilarity": round(strongest_anchor_similarity, 4),
                    "centroidSimilarity": round(centroid_similarity, 4),
                    "rank": 0,
                    "cropKind": crop.crop_kind,
                }
            )
        ranked_candidates.sort(key=lambda item: float(item["score"]), reverse=True)
        for rank, candidate in enumerate(ranked_candidates, start=1):
            candidate["rank"] = rank
        return ranked_candidates

    def _normalize_cluster_members(
        self,
        *,
        clusters: list[ClusterSummary],
        assignments: list[ClusterAssignmentResult],
        cluster_anchor_vectors: dict[int, np.ndarray],
    ) -> list[ClusterSummary]:
        member_lists: dict[int, list[str]] = {cluster.cluster_index: list(cluster.anchor_crop_ids) for cluster in clusters}
        for assignment in assignments:
            if assignment.cluster_index is None:
                continue
            if assignment.state not in {"auto_confirmed", "manual"}:
                continue
            if assignment.crop_id not in member_lists[assignment.cluster_index]:
                member_lists[assignment.cluster_index].append(assignment.crop_id)

        merge_warnings = self._merge_warning_pairs(clusters=clusters, cluster_anchor_vectors=cluster_anchor_vectors)
        merge_warning_indexes = {index for pair in merge_warnings for index in pair}
        normalized: list[ClusterSummary] = []
        for cluster in clusters:
            review_flags = list(cluster.review_flags)
            if cluster.cluster_index in merge_warning_indexes and "possible_merge" not in review_flags:
                review_flags.append("possible_merge")
            if cluster.confidence < 0.78 and "low_confidence" not in review_flags:
                review_flags.append("low_confidence")
            normalized.append(
                ClusterSummary(
                    cluster_index=cluster.cluster_index,
                    anchor_crop_ids=cluster.anchor_crop_ids,
                    member_crop_ids=member_lists[cluster.cluster_index],
                    confidence=cluster.confidence,
                    review_flags=review_flags,
                    diagnostics={
                        **cluster.diagnostics,
                        "possibleMergeClusterIndexes": sorted(
                            other
                            for left, right in merge_warnings
                            for other in ((right,) if left == cluster.cluster_index else (left,) if right == cluster.cluster_index else ())
                        ),
                    },
                )
            )
        return normalized

    def _anchor_assignment_state(self, crop: ClusterInputCrop, cluster: ClusterSummary) -> str:
        kinds = set(cluster.diagnostics.get("anchorKinds", []))
        if crop.crop_kind in CONTEXT_ONLY_KINDS:
            return "suggested"
        if kinds and kinds.issubset(CONTEXT_ONLY_KINDS | {"heuristic"}):
            return "suggested"
        if crop.crop_kind == "heuristic":
            return "suggested"
        if crop.crop_kind in IDENTITY_STRONG_KINDS:
            return "auto_confirmed"
        return "auto_confirmed" if cluster.confidence >= 0.82 else "suggested"

    def _can_attach_auto(self, *, crop: ClusterInputCrop, top_score: float, margin_score: float) -> bool:
        if crop.crop_kind not in IDENTITY_STRONG_KINDS:
            return False
        return top_score >= FACE_ATTACH_SIMILARITY_THRESHOLD and margin_score >= FACE_ATTACH_MARGIN_THRESHOLD

    def _unknown_assignment(self, crop: ClusterInputCrop) -> ClusterAssignmentResult:
        return ClusterAssignmentResult(
            crop_id=crop.crop_id,
            cluster_index=None,
            state="unknown",
            score=0.0,
            margin_score=0.0,
            ranked_candidates=[],
        )

    def _score_against_cluster(self, *, crop: ClusterInputCrop, cluster_crops: list[ClusterInputCrop]) -> tuple[float, float, float]:
        anchor_vectors = np.stack([item.vector for item in cluster_crops], axis=0)
        centroid = self._centroid(anchor_vectors)
        centroid_similarity = float(np.dot(crop.vector, centroid))
        strongest_anchor_similarity = float(np.max(anchor_vectors @ crop.vector))
        score = (centroid_similarity * 0.55) + (strongest_anchor_similarity * 0.45)
        return score, centroid_similarity, strongest_anchor_similarity

    def _cluster_confidence(self, vectors: np.ndarray) -> float:
        if vectors.shape[0] == 1:
            return 0.52
        pairwise = vectors @ vectors.T
        upper = pairwise[np.triu_indices(pairwise.shape[0], k=1)]
        if upper.size == 0:
            return 0.52
        average = float(np.mean(upper))
        minimum = float(np.min(upper))
        variance_penalty = float(np.std(upper) * 0.24)
        confidence = max(0.34, min(0.98, (average * 0.65) + (minimum * 0.35) - variance_penalty))
        return round(confidence, 4)

    def _merge_warning_pairs(
        self,
        *,
        clusters: list[ClusterSummary],
        cluster_anchor_vectors: dict[int, np.ndarray],
    ) -> set[tuple[int, int]]:
        warnings: set[tuple[int, int]] = set()
        for index, left in enumerate(clusters):
            left_centroid = self._centroid(cluster_anchor_vectors[left.cluster_index])
            for right in clusters[index + 1 :]:
                right_centroid = self._centroid(cluster_anchor_vectors[right.cluster_index])
                similarity = float(np.dot(left_centroid, right_centroid))
                if similarity >= 0.90:
                    warnings.add((left.cluster_index, right.cluster_index))
        return warnings

    def _centroid(self, vectors: np.ndarray) -> np.ndarray:
        centroid = vectors.mean(axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm <= 1e-6:
            return centroid
        return centroid / norm

    def _cosine_distance_matrix(self, *, vectors: np.ndarray, crops: list[ClusterInputCrop]) -> np.ndarray:
        similarity = np.clip(vectors @ vectors.T, -1.0, 1.0)
        distances = 1.0 - similarity
        for left_index, left_crop in enumerate(crops):
            for right_index, right_crop in enumerate(crops[left_index + 1 :], start=left_index + 1):
                if left_crop.panel_id == right_crop.panel_id:
                    distances[left_index, right_index] = 1.0
                    distances[right_index, left_index] = 1.0
        np.fill_diagonal(distances, 0.0)
        return distances
