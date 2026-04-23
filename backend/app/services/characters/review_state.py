from __future__ import annotations

from datetime import datetime, timezone

from app.models.characters import (
    ChapterCharacterState,
    CharacterCluster,
    CharacterCreateClusterRequest,
    CharacterMergeRequest,
    CharacterPanelMappingRequest,
    CharacterRenameRequest,
    CharacterStatusRequest,
    PanelCharacterRef,
)
from app.services.characters.repository import CharacterStateRepository


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CharacterReviewStateService:
    def __init__(self, repository: CharacterStateRepository) -> None:
        self.repository = repository

    def get(self, chapter_id: str) -> ChapterCharacterState | None:
        return self.repository.load(chapter_id)

    def create_manual_cluster(self, request: CharacterCreateClusterRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        cluster_index = len(state.clusters) + 1
        cluster_id = f"char_{cluster_index:03d}"
        display_label = request.displayLabel.strip() or request.canonicalName.strip() or f"nhan vat {cluster_index}"
        panel_ids = self._dedupe_list(request.panelIds)
        cluster = CharacterCluster(
            clusterId=cluster_id,
            chapterId=state.chapterId,
            status="locked" if request.lockName else "draft",
            canonicalName=request.canonicalName.strip(),
            displayLabel=display_label,
            lockName=request.lockName,
            confidenceScore=1.0 if panel_ids else 0.0,
            occurrenceCount=len(panel_ids),
            anchorPanelIds=panel_ids[:4],
            samplePanelIds=panel_ids[:8],
            reviewFlags=[],
        )
        state.clusters.append(cluster)
        if panel_ids:
            for panel_id in panel_ids:
                self._upsert_panel_ref(
                    state,
                    PanelCharacterRef(
                        panelId=panel_id,
                        clusterIds=[cluster_id],
                        source="manual",
                        confidenceScore=1.0,
                    ),
                )
        return self._save(state)

    def rename_cluster(self, request: CharacterRenameRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        cluster = self._require_cluster(state, request.clusterId)
        cluster.canonicalName = request.canonicalName.strip()
        if cluster.canonicalName and (cluster.lockName or not cluster.displayLabel.strip()):
            cluster.displayLabel = cluster.canonicalName
        cluster.lockName = request.lockName
        cluster.status = "locked" if request.lockName else "draft"
        if "review_needed" in cluster.reviewFlags and cluster.canonicalName:
            cluster.reviewFlags = [flag for flag in cluster.reviewFlags if flag != "review_needed"]
        return self._save(state)

    def merge_clusters(self, request: CharacterMergeRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        source = self._require_cluster(state, request.sourceClusterId)
        target = self._require_cluster(state, request.targetClusterId)
        if source.clusterId == target.clusterId:
            return state

        target_panel_ids = self._dedupe_list([*target.samplePanelIds, *source.samplePanelIds])
        target_anchor_ids = self._dedupe_list([*target.anchorPanelIds, *source.anchorPanelIds])
        target.samplePanelIds = target_panel_ids[:8]
        target.anchorPanelIds = target_anchor_ids[:4]
        target.occurrenceCount = len(target_panel_ids)
        target.confidenceScore = max(target.confidenceScore, source.confidenceScore)
        if not target.canonicalName.strip() and source.canonicalName.strip():
            target.canonicalName = source.canonicalName
        if not target.displayLabel.strip():
            target.displayLabel = source.displayLabel

        source.status = "merged"
        source.lockName = False
        source.mergedIntoClusterId = target.clusterId
        source.reviewFlags = self._dedupe_list([*source.reviewFlags, "merged"])

        for ref in state.panelCharacterRefs:
            if source.clusterId not in ref.clusterIds:
                continue
            next_ids = [target.clusterId if cluster_id == source.clusterId else cluster_id for cluster_id in ref.clusterIds]
            ref.clusterIds = self._dedupe_list(next_ids)
            ref.source = "manual"
            ref.confidenceScore = max(ref.confidenceScore, target.confidenceScore)

        return self._save(state)

    def update_panel_mapping(self, request: CharacterPanelMappingRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        active_cluster_ids = {
            cluster.clusterId
            for cluster in state.clusters
            if cluster.status not in {"ignored", "merged"}
        }
        cluster_ids = [cluster_id for cluster_id in self._dedupe_list(request.clusterIds) if cluster_id in active_cluster_ids]
        ref = PanelCharacterRef(
            panelId=request.panelId,
            clusterIds=cluster_ids,
            source="manual" if cluster_ids else "unknown",
            confidenceScore=1.0 if cluster_ids else 0.0,
        )
        self._upsert_panel_ref(state, ref)
        for cluster in state.clusters:
            if cluster.clusterId in cluster_ids:
                if request.panelId not in cluster.samplePanelIds:
                    cluster.samplePanelIds.append(request.panelId)
                if request.panelId not in cluster.anchorPanelIds and len(cluster.anchorPanelIds) < 4:
                    cluster.anchorPanelIds.append(request.panelId)
                cluster.occurrenceCount = len(self._dedupe_list(cluster.samplePanelIds))
        return self._save(state)

    def update_cluster_status(self, request: CharacterStatusRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        cluster = self._require_cluster(state, request.clusterId)
        cluster.status = request.status
        if request.status in {"unknown", "ignored"}:
            cluster.lockName = False
        return self._save(state)

    def _require_state(self, chapter_id: str) -> ChapterCharacterState:
        state = self.repository.load(chapter_id)
        if state is None:
            raise ValueError(f"Character state not found for chapter_id '{chapter_id}'.")
        return state

    def _require_cluster(self, state: ChapterCharacterState, cluster_id: str) -> CharacterCluster:
        for cluster in state.clusters:
            if cluster.clusterId == cluster_id:
                return cluster
        raise ValueError(f"Character cluster '{cluster_id}' not found for chapter_id '{state.chapterId}'.")

    def _upsert_panel_ref(self, state: ChapterCharacterState, next_ref: PanelCharacterRef) -> None:
        for index, ref in enumerate(state.panelCharacterRefs):
            if ref.panelId == next_ref.panelId:
                state.panelCharacterRefs[index] = next_ref
                return
        state.panelCharacterRefs.append(next_ref)

    def _save(self, state: ChapterCharacterState) -> ChapterCharacterState:
        state.updatedAt = _utc_now()
        state.needsReview = any(
            not ref.clusterIds
            or any(
                "review_needed" in cluster.reviewFlags
                for cluster in state.clusters
                if cluster.clusterId in ref.clusterIds
            )
            for ref in state.panelCharacterRefs
        )
        return self.repository.save(state)

    def _dedupe_list(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result
