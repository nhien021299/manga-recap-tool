from typing import Literal

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
from app.models.render_jobs import RenderJobLogEntry, RenderJobStatus


class ScriptJobOptions(BaseModel):
    reuseCache: bool = True
    returnRawOutputs: bool = True


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


class HealthResponse(BaseModel):
    status: str = "ok"


class VoiceOption(BaseModel):
    key: str
    label: str
    provider: str
    isAvailable: bool = False
    sampleRate: int | None = None
    speakerCount: int = 1
    quality: str = ""
    description: str = ""
    styleTag: str | None = None
    sampleUrl: str | None = None
    statusMessage: str | None = None


class VoiceProviderOption(BaseModel):
    id: str
    label: str
    enabled: bool = False
    defaultVoiceKey: str | None = None
    statusMessage: str | None = None
    voices: list[VoiceOption] = Field(default_factory=list)


class VoiceOptionsResponse(BaseModel):
    defaultProvider: str
    providers: list[VoiceProviderOption] = Field(default_factory=list)


class VoiceGenerateRequest(BaseModel):
    text: str
    provider: str = "vieneu"
    voiceKey: str
    speed: float = 1.15


class TtsRuntimeResponse(BaseModel):
    provider: str
    requestedRuntime: str
    resolvedRuntime: str
    executionProvider: str
    fallbackActive: bool = False
    supportsGpu: bool = False
    deviceName: str
    platform: str
    modelSource: str
    modelPath: str | None = None
    modelBundle: str | None = None
    runtimePython: str | None = None
    availableProviders: list[str] = Field(default_factory=list)
    warm: bool = False
    isAvailable: bool = False
    startupError: str | None = None


class RenderClipSpec(BaseModel):
    clipId: str
    panelId: str
    orderIndex: int
    durationMs: int = Field(gt=0)
    holdAfterMs: int = Field(default=0, ge=0)
    captionText: str = ""
    panelFileKey: str
    audioFileKey: str | None = None
    motionPreset: str | None = None
    motionSeed: int | None = None
    motionIntensity: float | None = Field(default=None, ge=0.0, le=1.5)


class RenderPlanRequest(BaseModel):
    outputWidth: int = Field(gt=0)
    outputHeight: int = Field(gt=0)
    captionMode: Literal["off", "burned"] = "off"
    frameRate: int = Field(default=30, ge=12, le=60)


class RenderJobCreateResponse(BaseModel):
    jobId: str
    status: RenderJobStatus


class RenderJobStatusResponse(BaseModel):
    jobId: str
    status: RenderJobStatus
    progress: int
    phase: str
    detail: str | None = None
    downloadUrl: str | None = None
    error: str | None = None
    logs: list[RenderJobLogEntry] = Field(default_factory=list)


class RenderRevealResponse(BaseModel):
    success: bool = True
