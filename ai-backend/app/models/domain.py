from pydantic import BaseModel, Field


class ScriptContext(BaseModel):
    mangaName: str
    mainCharacter: str
    summary: str = ""
    language: str = "vi"


class PanelReference(BaseModel):
    panelId: str
    orderIndex: int


class OCRLine(BaseModel):
    text: str
    confidence: float = 0.0
    role: str = "unknown"
    bbox: list[int] = Field(default_factory=list)


class OCRResult(BaseModel):
    panel_id: str
    lines: list[OCRLine] = Field(default_factory=list)
    full_text: str = ""
    has_text: bool = False


class VisionCaptionRaw(BaseModel):
    panel_index: int
    panel_id: str = ""
    main_event: str = ""
    inset_event: str = ""
    visible_objects: list[str] = Field(default_factory=list)
    visible_text: list[str] = Field(default_factory=list)
    sfx_guess: list[str] = Field(default_factory=list)
    scene_tone: str = ""


class MergeDiagnostics(BaseModel):
    correction_tags: list[str] = Field(default_factory=list)
    ocr_has_text: bool = False
    ocr_line_count: int = 0
    caption_source: str = "vision_only"


class PanelUnderstanding(BaseModel):
    panelId: str
    orderIndex: int
    summary: str = ""
    main_event: str = ""
    inset_event: str = ""
    visible_objects: list[str] = Field(default_factory=list)
    visible_text: list[str] = Field(default_factory=list)
    scene_tone: str = ""
    action: str = ""
    emotion: str = ""
    dialogue: str = ""
    sfx: list[str] = Field(default_factory=list)
    cliffhanger: str = ""
    narrative_hook: str = ""


class ScriptItem(BaseModel):
    panel_index: int
    ai_view: str
    voiceover_text: str
    sfx: list[str] = Field(default_factory=list)


class StoryMemory(BaseModel):
    chunkIndex: int
    summary: str


class CaptionDraft(BaseModel):
    panel_index: int
    summary: str = ""
    main_event: str = ""
    inset_event: str = ""
    visible_objects: list[str] = Field(default_factory=list)
    visible_text: list[str] = Field(default_factory=list)
    scene_tone: str = ""
    action: str = ""
    emotion: str = ""
    dialogue: str = ""
    sfx: list[str] = Field(default_factory=list)
    cliffhanger: str = ""
    narrative_hook: str = ""


class CaptionBatchOutput(BaseModel):
    items: list[CaptionDraft]


class VisionCaptionBatchOutput(BaseModel):
    items: list[VisionCaptionRaw]


class ScriptDraft(BaseModel):
    panel_index: int
    ai_view: str = ""
    voiceover_text: str = ""
    sfx: list[str] = Field(default_factory=list)


class ScriptChunkOutput(BaseModel):
    items: list[ScriptDraft]


class StoryMemoryOutput(BaseModel):
    summary: str


class RawOutputs(BaseModel):
    understanding: str = ""
    script: str = ""


class Metrics(BaseModel):
    panelCount: int
    totalMs: int
    captionMs: int
    ocrMs: int = 0
    mergeMs: int = 0
    scriptMs: int
    avgPanelMs: float = 0.0
    captionSource: str = "vision_only"
