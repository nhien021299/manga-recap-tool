from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


CharacterClusterStatus = Literal["draft", "locked", "review_needed", "unknown", "ignored", "merged"]
PanelCharacterSource = Literal["auto_confirmed", "manual", "unknown", "suggested"]


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
    anchorPanelIds: list[str] = Field(default_factory=list)
    samplePanelIds: list[str] = Field(default_factory=list)
    reviewFlags: list[str] = Field(default_factory=list)
    mergedIntoClusterId: str | None = None

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
    prepassVersion: str = "heuristic-panel-v1"
    generatedAt: str = ""
    updatedAt: str = ""
    needsReview: bool = True
    clusters: list[CharacterCluster] = Field(default_factory=list)
    panelCharacterRefs: list[PanelCharacterRef] = Field(default_factory=list)


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
    panelIds: list[str] = Field(default_factory=list)


class CharacterStatusRequest(BaseModel):
    chapterId: str
    clusterId: str
    status: Literal["draft", "unknown", "ignored"]

