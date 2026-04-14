from pydantic import BaseModel, Field


class ScriptContext(BaseModel):
    mangaName: str
    mainCharacter: str
    summary: str = ""
    language: str = "vi"


class PanelReference(BaseModel):
    panelId: str
    orderIndex: int


class PanelUnderstanding(BaseModel):
    panelId: str
    orderIndex: int
    summary: str = ""
    action: str = ""
    emotion: str = ""
    dialogue: str = ""
    sfx: list[str] = Field(default_factory=list)
    cliffhanger: str = ""


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
    action: str = ""
    emotion: str = ""
    dialogue: str = ""
    sfx: list[str] = Field(default_factory=list)
    cliffhanger: str = ""


class CaptionBatchOutput(BaseModel):
    items: list[CaptionDraft]


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
    scriptMs: int
