from __future__ import annotations

from datetime import datetime, timezone

from app.models.characters import (
    ChapterCharacterState,
    CharacterCandidateAssignment,
    CharacterCluster,
    CharacterCreateClusterRequest,
    CharacterCrop,
    CharacterCropMappingRequest,
    CharacterMergeRequest,
    CharacterPanelMappingRequest,
    CharacterRenameRequest,
    CharacterSplitRequest,
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
        crop_ids = [crop.cropId for crop in self._resolve_crops_for_manual_cluster(state, request)]
        panel_ids = self._dedupe_list(
            request.panelIds + [self._require_crop(state, crop_id).panelId for crop_id in crop_ids]
        )
        display_label = request.displayLabel.strip() or request.canonicalName.strip() or f"nhan vat {cluster_index}"
        cluster = CharacterCluster(
            clusterId=cluster_id,
            chapterId=state.chapterId,
            status="locked" if request.lockName else "draft",
            canonicalName=request.canonicalName.strip(),
            displayLabel=display_label,
            lockName=request.lockName,
            confidenceScore=1.0 if crop_ids else 0.0,
            occurrenceCount=len(panel_ids),
            anchorCropIds=crop_ids[:6],
            anchorPanelIds=panel_ids[:4],
            samplePanelIds=panel_ids[:8],
            reviewFlags=[],
        )
        state.clusters.append(cluster)

        if crop_ids:
            for crop_id in crop_ids:
                self._assign_crop(state=state, crop_id=crop_id, cluster_id=cluster_id, state_name="manual", score=1.0)
        elif panel_ids:
            for panel_id in panel_ids:
                self._upsert_panel_ref(
                    state,
                    PanelCharacterRef(
                        panelId=panel_id,
                        clusterIds=[cluster_id],
                        source="manual",
                        confidenceScore=1.0,
                        diagnostics={"manualOverride": True},
                    ),
                )

        return self._save(state)

    def rename_cluster(self, request: CharacterRenameRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        cluster = self._require_cluster(state, request.clusterId)
        cluster.canonicalName = request.canonicalName.strip()
        if cluster.canonicalName and (request.lockName or not cluster.displayLabel.strip()):
            cluster.displayLabel = cluster.canonicalName
        cluster.lockName = request.lockName
        cluster.status = "locked" if request.lockName else "draft"
        cluster.reviewFlags = [flag for flag in cluster.reviewFlags if flag != "review_needed"] if cluster.canonicalName else cluster.reviewFlags
        return self._save(state)

    def merge_clusters(self, request: CharacterMergeRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        source = self._require_cluster(state, request.sourceClusterId)
        target = self._require_cluster(state, request.targetClusterId)
        if source.clusterId == target.clusterId:
            return state

        target.anchorCropIds = self._dedupe_list([*target.anchorCropIds, *source.anchorCropIds])[:6]
        target.anchorPanelIds = self._dedupe_list([*target.anchorPanelIds, *source.anchorPanelIds])[:4]
        target.samplePanelIds = self._dedupe_list([*target.samplePanelIds, *source.samplePanelIds])[:8]
        target.confidenceScore = max(target.confidenceScore, source.confidenceScore)
        target.reviewFlags = self._dedupe_list(
            [
                *target.reviewFlags,
                *(flag for flag in source.reviewFlags if flag not in {"merged"}),
            ]
        )
        if not target.canonicalName.strip() and source.canonicalName.strip():
            target.canonicalName = source.canonicalName
        if not target.displayLabel.strip():
            target.displayLabel = source.displayLabel

        source.status = "merged"
        source.lockName = False
        source.mergedIntoClusterId = target.clusterId
        source.reviewFlags = self._dedupe_list([*source.reviewFlags, "merged"])

        for crop in state.crops:
            if crop.assignedClusterId == source.clusterId:
                crop.assignedClusterId = target.clusterId

        next_assignments: list[CharacterCandidateAssignment] = []
        seen_assignment_keys: set[tuple[str, str, int]] = set()
        for assignment in state.candidateAssignments:
            cluster_id = target.clusterId if assignment.clusterId == source.clusterId else assignment.clusterId
            key = (assignment.cropId, cluster_id, assignment.rank)
            if key in seen_assignment_keys:
                continue
            seen_assignment_keys.add(key)
            next_assignments.append(
                CharacterCandidateAssignment(
                    cropId=assignment.cropId,
                    panelId=assignment.panelId,
                    clusterId=cluster_id,
                    rank=assignment.rank,
                    score=assignment.score,
                    marginScore=assignment.marginScore,
                    state=assignment.state,
                    diagnostics=assignment.diagnostics,
                )
            )
        state.candidateAssignments = next_assignments

        for ref in state.panelCharacterRefs:
            if source.clusterId not in ref.clusterIds:
                continue
            ref.clusterIds = self._dedupe_list(
                [target.clusterId if cluster_id == source.clusterId else cluster_id for cluster_id in ref.clusterIds]
            )
            ref.source = "manual"
            ref.confidenceScore = max(ref.confidenceScore, target.confidenceScore)
            ref.diagnostics = {**ref.diagnostics, "manualOverride": True}

        return self._save(state)

    def split_cluster(self, request: CharacterSplitRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        source = self._require_cluster(state, request.sourceClusterId)
        if source.status in {"ignored", "merged"}:
            raise ValueError(f"Character cluster '{source.clusterId}' is not active.")

        split_crops = self._resolve_crops_for_split(state, request)
        if not split_crops and request.panelIds:
            for panel_id in request.panelIds:
                self._upsert_panel_ref(
                    state,
                    PanelCharacterRef(
                        panelId=panel_id,
                        clusterIds=[],
                        source="unknown",
                        confidenceScore=0.0,
                        diagnostics={"manualOverride": True, "splitFromClusterId": source.clusterId},
                    ),
                )
            return self._save(state)
        if not split_crops:
            raise ValueError("Split requires at least one crop or panel with crops from the source cluster.")

        cluster_id = self._next_cluster_id(state)
        panel_ids = self._dedupe_list([crop.panelId for crop in split_crops])
        canonical_name = request.canonicalName.strip()
        display_label = canonical_name or f"{source.displayLabel or source.clusterId} split"
        cluster = CharacterCluster(
            clusterId=cluster_id,
            chapterId=state.chapterId,
            status="locked" if canonical_name else "draft",
            canonicalName=canonical_name,
            displayLabel=display_label,
            lockName=bool(canonical_name),
            confidenceScore=1.0,
            occurrenceCount=len(panel_ids),
            anchorCropIds=[crop.cropId for crop in split_crops[:6]],
            anchorPanelIds=panel_ids[:4],
            samplePanelIds=panel_ids[:8],
            reviewFlags=[],
            diagnostics={"splitFromClusterId": source.clusterId},
        )
        state.clusters.append(cluster)

        split_crop_ids = {crop.cropId for crop in split_crops}
        for crop in split_crops:
            self._assign_crop(state=state, crop_id=crop.cropId, cluster_id=cluster_id, state_name="manual", score=1.0)

        source.anchorCropIds = [crop_id for crop_id in source.anchorCropIds if crop_id not in split_crop_ids]
        source.samplePanelIds = [
            panel_id
            for panel_id in source.samplePanelIds
            if any(crop.panelId == panel_id and crop.assignedClusterId == source.clusterId for crop in state.crops)
        ]
        source.anchorPanelIds = [
            panel_id
            for panel_id in source.anchorPanelIds
            if any(crop.panelId == panel_id and crop.cropId in source.anchorCropIds for crop in state.crops)
        ]
        source.reviewFlags = self._dedupe_list([*source.reviewFlags, "split_reviewed"])

        for panel_id in panel_ids:
            ref = next((item for item in state.panelCharacterRefs if item.panelId == panel_id), None)
            cluster_ids = list(ref.clusterIds) if ref is not None else []
            cluster_ids = [cluster_id if item == source.clusterId else item for item in cluster_ids]
            if cluster_id not in cluster_ids:
                cluster_ids.append(cluster_id)
            if any(crop.panelId == panel_id and crop.assignedClusterId == source.clusterId for crop in state.crops):
                cluster_ids.append(source.clusterId)
            self._upsert_panel_ref(
                state,
                PanelCharacterRef(
                    panelId=panel_id,
                    clusterIds=self._dedupe_list(cluster_ids),
                    source="manual",
                    confidenceScore=1.0,
                    diagnostics={"manualOverride": True, "splitFromClusterId": source.clusterId},
                ),
            )

        return self._save(state)

    def update_panel_mapping(self, request: CharacterPanelMappingRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        active_cluster_ids = {
            cluster.clusterId
            for cluster in state.clusters
            if cluster.status not in {"ignored", "merged", "unknown"}
        }
        cluster_ids = [cluster_id for cluster_id in self._dedupe_list(request.clusterIds) if cluster_id in active_cluster_ids]
        self._upsert_panel_ref(
            state,
            PanelCharacterRef(
                panelId=request.panelId,
                clusterIds=cluster_ids,
                source="manual" if cluster_ids else "unknown",
                confidenceScore=1.0 if cluster_ids else 0.0,
                diagnostics={"manualOverride": True},
            ),
        )
        for cluster in state.clusters:
            if cluster.clusterId in cluster_ids and request.panelId not in cluster.samplePanelIds:
                cluster.samplePanelIds.append(request.panelId)
        return self._save(state)

    def update_crop_mapping(self, request: CharacterCropMappingRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        crop = self._require_crop(state, request.cropId)
        if request.clusterId is None:
            crop.assignedClusterId = None
            crop.assignmentState = "unknown"
            state.candidateAssignments = [assignment for assignment in state.candidateAssignments if assignment.cropId != crop.cropId]
        else:
            cluster = self._require_cluster(state, request.clusterId)
            if cluster.status in {"ignored", "merged", "unknown"}:
                raise ValueError(f"Character cluster '{cluster.clusterId}' is not active.")
            self._assign_crop(state=state, crop_id=crop.cropId, cluster_id=cluster.clusterId, state_name="manual", score=1.0)
            if crop.cropId not in cluster.anchorCropIds and len(cluster.anchorCropIds) < 6:
                cluster.anchorCropIds.append(crop.cropId)
            if crop.panelId not in cluster.anchorPanelIds and len(cluster.anchorPanelIds) < 4:
                cluster.anchorPanelIds.append(crop.panelId)

        state.panelCharacterRefs = [
            ref for ref in state.panelCharacterRefs if not (ref.panelId == crop.panelId and ref.diagnostics.get("manualOverride"))
        ]
        return self._save(state)

    def update_cluster_status(self, request: CharacterStatusRequest) -> ChapterCharacterState:
        state = self._require_state(request.chapterId)
        cluster = self._require_cluster(state, request.clusterId)
        cluster.status = request.status
        if request.status in {"unknown", "ignored"}:
            cluster.lockName = False
            for crop in state.crops:
                if crop.assignedClusterId == cluster.clusterId:
                    crop.assignedClusterId = None
                    crop.assignmentState = "unknown"
            state.candidateAssignments = [
                assignment
                for assignment in state.candidateAssignments
                if assignment.clusterId != cluster.clusterId
            ]
            for ref in state.panelCharacterRefs:
                if cluster.clusterId not in ref.clusterIds:
                    continue
                ref.clusterIds = [item for item in ref.clusterIds if item != cluster.clusterId]
                if not ref.clusterIds:
                    ref.source = "unknown"
                    ref.confidenceScore = 0.0
                ref.diagnostics = {**ref.diagnostics, "statusClearedClusterId": cluster.clusterId}
        return self._save(state)

    def _assign_crop(self, *, state: ChapterCharacterState, crop_id: str, cluster_id: str, state_name: str, score: float) -> None:
        crop = self._require_crop(state, crop_id)
        crop.assignedClusterId = cluster_id
        crop.assignmentState = state_name
        state.candidateAssignments = [assignment for assignment in state.candidateAssignments if assignment.cropId != crop_id]
        state.candidateAssignments.append(
            CharacterCandidateAssignment(
                cropId=crop.cropId,
                panelId=crop.panelId,
                clusterId=cluster_id,
                rank=1,
                score=score,
                marginScore=1.0,
                state=state_name,
                diagnostics={"manual": state_name == "manual"},
            )
        )

    def _resolve_crops_for_manual_cluster(self, state: ChapterCharacterState, request: CharacterCreateClusterRequest) -> list[CharacterCrop]:
        crops: list[CharacterCrop] = []
        seen: set[str] = set()
        for crop_id in request.cropIds:
            crop = self._require_crop(state, crop_id)
            if crop.cropId in seen:
                continue
            seen.add(crop.cropId)
            crops.append(crop)
        for panel_id in request.panelIds:
            panel_crops = [crop for crop in state.crops if crop.panelId == panel_id]
            if not panel_crops:
                continue
            panel_crops.sort(key=lambda item: (-item.qualityScore, item.cropId))
            for crop in panel_crops:
                if crop.cropId in seen:
                    continue
                seen.add(crop.cropId)
                crops.append(crop)
                break
        return crops

    def _resolve_crops_for_split(self, state: ChapterCharacterState, request: CharacterSplitRequest) -> list[CharacterCrop]:
        source = self._require_cluster(state, request.sourceClusterId)
        source_panel_ids = set(source.samplePanelIds + source.anchorPanelIds)
        for ref in state.panelCharacterRefs:
            if source.clusterId in ref.clusterIds:
                source_panel_ids.add(ref.panelId)

        crops: list[CharacterCrop] = []
        seen: set[str] = set()
        for crop_id in request.cropIds:
            crop = self._require_crop(state, crop_id)
            if crop.assignedClusterId != source.clusterId and crop.panelId not in source_panel_ids:
                raise ValueError(f"Character crop '{crop.cropId}' does not belong to source cluster '{source.clusterId}'.")
            if crop.cropId not in seen:
                seen.add(crop.cropId)
                crops.append(crop)

        for panel_id in request.panelIds:
            panel_crops = [
                crop
                for crop in state.crops
                if crop.panelId == panel_id and (crop.assignedClusterId == source.clusterId or panel_id in source_panel_ids)
            ]
            panel_crops.sort(key=lambda item: (item.assignedClusterId != source.clusterId, -item.qualityScore, item.cropId))
            for crop in panel_crops:
                if crop.cropId in seen:
                    continue
                seen.add(crop.cropId)
                crops.append(crop)
        return crops

    def _next_cluster_id(self, state: ChapterCharacterState) -> str:
        existing = {cluster.clusterId for cluster in state.clusters}
        index = len(existing) + 1
        while f"char_{index:03d}" in existing:
            index += 1
        return f"char_{index:03d}"

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

    def _require_crop(self, state: ChapterCharacterState, crop_id: str) -> CharacterCrop:
        for crop in state.crops:
            if crop.cropId == crop_id:
                return crop
        raise ValueError(f"Character crop '{crop_id}' not found for chapter_id '{state.chapterId}'.")

    def _upsert_panel_ref(self, state: ChapterCharacterState, next_ref: PanelCharacterRef) -> None:
        for index, ref in enumerate(state.panelCharacterRefs):
            if ref.panelId == next_ref.panelId:
                state.panelCharacterRefs[index] = next_ref
                return
        state.panelCharacterRefs.append(next_ref)

    def _save(self, state: ChapterCharacterState) -> ChapterCharacterState:
        state.updatedAt = _utc_now()
        state.panelCharacterRefs = self._rebuild_panel_refs(state)
        state.unresolvedPanelIds = self._rebuild_unresolved_panels(state)
        state.clusterDiagnostics = {
            cluster.clusterId: {
                "status": cluster.status,
                "reviewFlags": cluster.reviewFlags,
                "anchorCropIds": cluster.anchorCropIds,
            }
            for cluster in state.clusters
        }
        for cluster in state.clusters:
            assigned_panels = self._dedupe_list(
                [
                    crop.panelId
                    for crop in state.crops
                    if crop.assignedClusterId == cluster.clusterId and crop.assignmentState in {"auto_confirmed", "suggested", "manual"}
                ]
            )
            cluster.samplePanelIds = self._dedupe_list([*cluster.samplePanelIds, *assigned_panels])[:8]
            cluster.anchorPanelIds = self._dedupe_list(
                [*cluster.anchorPanelIds, *(self._require_crop(state, crop_id).panelId for crop_id in cluster.anchorCropIds if any(c.cropId == crop_id for c in state.crops))]
            )[:4]
            cluster.occurrenceCount = len(cluster.samplePanelIds)

        state.needsReview = bool(
            state.unresolvedPanelIds
            or any(
                cluster.status not in {"merged", "ignored"}
                and cluster.status != "unknown"
                and any(flag in {"review_needed", "possible_merge", "low_confidence"} for flag in cluster.reviewFlags)
                for cluster in state.clusters
            )
        )
        return self.repository.save(state)

    def _rebuild_panel_refs(self, state: ChapterCharacterState) -> list[PanelCharacterRef]:
        manual_overrides = {
            ref.panelId: ref
            for ref in state.panelCharacterRefs
            if ref.diagnostics.get("manualOverride")
        }
        rebuilt: list[PanelCharacterRef] = []
        panel_ids = self._dedupe_list([crop.panelId for crop in state.crops] + [ref.panelId for ref in state.panelCharacterRefs])
        active_cluster_ids = {
            cluster.clusterId
            for cluster in state.clusters
            if cluster.status not in {"ignored", "merged", "unknown"}
        }
        for panel_id in panel_ids:
            if panel_id in manual_overrides:
                rebuilt.append(manual_overrides[panel_id])
                continue
            panel_crops = [crop for crop in state.crops if crop.panelId == panel_id]
            cluster_ids = self._dedupe_list(
                [
                    crop.assignedClusterId or ""
                    for crop in panel_crops
                    if crop.assignedClusterId and crop.assignmentState in {"auto_confirmed", "manual"} and crop.assignedClusterId in active_cluster_ids
                ]
            )
            score_values = [
                assignment.score
                for assignment in state.candidateAssignments
                if assignment.panelId == panel_id and assignment.rank == 1 and assignment.clusterId in cluster_ids
            ]
            rebuilt.append(
                PanelCharacterRef(
                    panelId=panel_id,
                    clusterIds=cluster_ids,
                    source="manual" if any(crop.assignmentState == "manual" for crop in panel_crops) else "auto_confirmed" if cluster_ids else "unknown",
                    confidenceScore=round(sum(score_values) / len(score_values), 4) if score_values else (1.0 if cluster_ids else 0.0),
                    diagnostics={
                        "cropIds": [crop.cropId for crop in panel_crops],
                        "suggestedCropIds": [crop.cropId for crop in panel_crops if crop.assignmentState == "suggested"],
                    },
                )
            )
        rebuilt.sort(key=lambda item: next((crop.orderIndex for crop in state.crops if crop.panelId == item.panelId), 0))
        return rebuilt

    def _rebuild_unresolved_panels(self, state: ChapterCharacterState) -> list[str]:
        panel_ref_map = {ref.panelId: ref for ref in state.panelCharacterRefs}
        unresolved: list[str] = []
        for panel_id in self._dedupe_list([crop.panelId for crop in state.crops] + [ref.panelId for ref in state.panelCharacterRefs]):
            ref = panel_ref_map.get(panel_id)
            if ref is not None and ref.diagnostics.get("manualOverride") and ref.clusterIds:
                continue
            panel_crops = [crop for crop in state.crops if crop.panelId == panel_id]
            if not panel_crops:
                if ref is None or not ref.clusterIds:
                    unresolved.append(panel_id)
                continue
            if any(crop.assignmentState in {"suggested", "unknown"} for crop in panel_crops):
                unresolved.append(panel_id)
                continue
            if ref is None or not ref.clusterIds:
                unresolved.append(panel_id)
        return unresolved

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
