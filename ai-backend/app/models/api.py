from pydantic import BaseModel, Field

from app.models.domain import (
    Metrics,
    PanelReference,
    PanelUnderstanding,
    RawOutputs,
    ScriptContext,
    ScriptItem,
    StoryMemory,
)
from app.models.jobs import JobLogEntry, JobStatus


class ScriptJobOptions(BaseModel):
    reuseCache: bool = True
    returnRawOutputs: bool = True


class CaptionBatchRequest(BaseModel):
    context: ScriptContext
    panels: list[PanelReference]


class ScriptJobRequest(BaseModel):
    context: ScriptContext
    panels: list[PanelReference]
    options: ScriptJobOptions = Field(default_factory=ScriptJobOptions)


class ScriptJobResult(BaseModel):
    understandings: list[PanelUnderstanding]
    generatedItems: list[ScriptItem]
    storyMemories: list[StoryMemory]
    panelSignature: str
    rawOutputs: RawOutputs | None = None
    metrics: Metrics


class ScriptGenerationResponse(BaseModel):
    result: ScriptJobResult | None = None
    logs: list[JobLogEntry] = Field(default_factory=list)
    error: str | None = None


class CreateJobResponse(BaseModel):
    jobId: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    jobId: str
    status: JobStatus
    progress: int
    error: str | None = None
    logs: list[JobLogEntry] = Field(default_factory=list)


class ProvidersResponse(BaseModel):
    textProvider: str
    textModel: str
    visionProvider: str
    visionModel: str
    ocrEnabled: bool
    ocrProvider: str


class HealthResponse(BaseModel):
    status: str = "ok"
