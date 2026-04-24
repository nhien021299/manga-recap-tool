from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


CharacterClusterStatus = Literal["draft", "locked", "review_needed", "unknown", "ignored", "merged"]
PanelCharacterSource = Literal["auto_confirmed", "manual", "unknown", "suggested"]
CharacterQualityBucket = Literal["good", "medium", "poor"]
CharacterCropAssignmentState = Literal["auto_confirmed", "suggested", "manual", "unknown"]
CharacterCropKind = Literal["face", "head", "upper_body", "person", "accessory", "heuristic", "monster", "unknown"]


class CharacterPanelReference(BaseModel):
    panelId: str
    orderIndex: int


class CharacterCluster(BaseModel):
    clusterId: str
    chapterId: str
    status: CharacterClusterStatus = "draft"
    canonicalName: str = ""
    displayLabel: str = ""
    lockName: bool = False
    confidenceScore: float = 0.0
    occurrenceCount: int = 0
    anchorCropIds: list[str] = Field(default_factory=list)
    anchorPanelIds: list[str] = Field(default_factory=list)
    samplePanelIds: list[str] = Field(default_factory=list)
    reviewFlags: list[str] = Field(default_factory=list)
    mergedIntoClusterId: str | None = None
    diagnostics: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize_locked_status(self) -> "CharacterCluster":
        if self.lockName and self.status not in {"merged", "ignored"}:
            self.status = "locked"
        if not self.displayLabel:
            self.displayLabel = self.canonicalName.strip()
        return self


class PanelCharacterRef(BaseModel):
    panelId: str
    clusterIds: list[str] = Field(default_factory=list)
    source: PanelCharacterSource = "unknown"
    confidenceScore: float = 0.0
    diagnostics: dict[str, object] = Field(default_factory=dict)


class CharacterCrop(BaseModel):
    cropId: str
    panelId: str
    orderIndex: int
    bbox: list[int] = Field(default_factory=list)
    detectionScore: float = 0.0
    kind: CharacterCropKind = "heuristic"
    detectorSource: str = "heuristic"
    detectorModel: str = ""
    qualityScore: float = 0.0
    qualityBucket: CharacterQualityBucket = "poor"
    previewImage: str = ""
    assignedClusterId: str | None = None
    assignmentState: CharacterCropAssignmentState = "unknown"
    diagnostics: dict[str, object] = Field(default_factory=dict)


class CharacterCandidateAssignment(BaseModel):
    cropId: str
    panelId: str
    clusterId: str
    rank: int = 1
    score: float = 0.0
    marginScore: float = 0.0
    state: CharacterCropAssignmentState = "suggested"
    diagnostics: dict[str, object] = Field(default_factory=dict)


class CharacterScriptEntry(BaseModel):
    clusterId: str
    canonicalName: str = ""
    displayLabel: str = ""
    lockName: bool = False


class CharacterScriptContext(BaseModel):
    chapterId: str = ""
    characters: list[CharacterScriptEntry] = Field(default_factory=list)
    panelCharacterRefs: dict[str, list[str]] = Field(default_factory=dict)
    unknownPanelIds: list[str] = Field(default_factory=list)


class ChapterCharacterState(BaseModel):
    chapterId: str
    chapterContentHash: str = ""
    prepassVersion: str = "character-hybrid-v3"
    generatedAt: str = ""
    updatedAt: str = ""
    needsReview: bool = True
    clusters: list[CharacterCluster] = Field(default_factory=list)
    crops: list[CharacterCrop] = Field(default_factory=list)
    candidateAssignments: list[CharacterCandidateAssignment] = Field(default_factory=list)
    panelCharacterRefs: list[PanelCharacterRef] = Field(default_factory=list)
    unresolvedPanelIds: list[str] = Field(default_factory=list)
    clusterDiagnostics: dict[str, object] = Field(default_factory=dict)
    diagnostics: dict[str, object] = Field(default_factory=dict)


class CharacterPrepassRequest(BaseModel):
    chapterId: str
    panels: list[CharacterPanelReference] = Field(default_factory=list)
    force: bool = False


class CharacterRenameRequest(BaseModel):
    chapterId: str
    clusterId: str
    canonicalName: str = ""
    lockName: bool = False


class CharacterMergeRequest(BaseModel):
    chapterId: str
    sourceClusterId: str
    targetClusterId: str


class CharacterPanelMappingRequest(BaseModel):
    chapterId: str
    panelId: str
    clusterIds: list[str] = Field(default_factory=list)


class CharacterCreateClusterRequest(BaseModel):
    chapterId: str
    canonicalName: str = ""
    displayLabel: str = ""
    lockName: bool = False
    cropIds: list[str] = Field(default_factory=list)
    panelIds: list[str] = Field(default_factory=list)


class CharacterStatusRequest(BaseModel):
    chapterId: str
    clusterId: str
    status: Literal["draft", "unknown", "ignored"]


class CharacterCropMappingRequest(BaseModel):
    chapterId: str
    cropId: str
    clusterId: str | None = None


class CharacterSplitRequest(BaseModel):
    chapterId: str
    sourceClusterId: str
    cropIds: list[str] = Field(default_factory=list)
    panelIds: list[str] = Field(default_factory=list)
    canonicalName: str = ""
