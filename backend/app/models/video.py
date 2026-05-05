"""Pydantic models for the video production pipeline.

Covers: narration input, batch TTS results, video direction from Gemini,
and orchestration job state.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input models (parsed from chapter_X_narration_tts.json)
# ---------------------------------------------------------------------------


class NarrationStyle(BaseModel):
    voice: str = ""
    tone: str = ""
    pacing: str = ""
    rules: list[str] = Field(default_factory=list)


class SceneInput(BaseModel):
    scene: int
    title: str
    status: str = ""
    image_path: str = ""
    duration_seconds: float
    narration: str
    retention_beat: str | None = None
    dialogue: str | None = None
    dialogue_speaker: str | None = None
    dialogue_timing: str = "after_narration"
    # Optional effect overrides from preset-driven plan
    scene_type: str | None = None
    mood: str | None = None
    motion_preset: str | None = None
    motion_intensity: float | None = None
    transition: str | None = None
    transition_duration_ms: int | None = None
    vfx_tags: list[str] = Field(default_factory=list)
    sfx_tags: list[str] = Field(default_factory=list)
    subtitle_mood: str | None = None


class NarrationPackage(BaseModel):
    project: str
    chapter: int
    language: str = "vi-VN"
    version: str = ""
    source: str = ""
    recommended_scene_count: int = 0
    narration_style: NarrationStyle | None = None
    scenes: list[SceneInput]


# ---------------------------------------------------------------------------
# Batch TTS results
# ---------------------------------------------------------------------------


class SceneTtsResult(BaseModel):
    scene: int
    title: str
    audio_path: str
    audio_duration_ms: int
    target_duration_ms: int
    visual_hold_ms: int = 0
    narration: str
    dialogue_audio_path: str | None = None
    dialogue_duration_ms: int | None = None


class BatchTtsResult(BaseModel):
    job_id: str
    total_scenes: int
    total_audio_duration_ms: int
    scene_results: list[SceneTtsResult]


# ---------------------------------------------------------------------------
# Batch TTS request
# ---------------------------------------------------------------------------


class BatchTtsRequest(BaseModel):
    narration_path: str
    voice_key: str = "voice_default"
    speed: float = 1.15
    provider: str = "vieneu"


# ---------------------------------------------------------------------------
# Video direction models (Gemini output → Remotion input)
# ---------------------------------------------------------------------------


class KeyframeEffect(BaseModel):
    time_pct: float = Field(ge=0.0, le=1.0)
    effect: str
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    easing: str = "ease_in_out"
    params: dict = Field(default_factory=dict)


class SceneTransition(BaseModel):
    type: str = "crossfade"
    duration_ms: int = Field(default=500, ge=0)
    params: dict = Field(default_factory=dict)


class TextOverlay(BaseModel):
    text: str
    start_pct: float = Field(ge=0.0, le=1.0)
    end_pct: float = Field(ge=0.0, le=1.0)
    style: str = "subtitle"
    position: str = "bottom_center"


class SceneDirection(BaseModel):
    scene: int
    total_duration_ms: int
    audio_start_ms: int = 0
    keyframes: list[KeyframeEffect] = Field(default_factory=list)
    transition_in: SceneTransition | None = None
    transition_out: SceneTransition = Field(default_factory=SceneTransition)
    text_overlays: list[TextOverlay] = Field(default_factory=list)
    color_grade: str = "neutral"
    motion_preset: str = "push_in_center"
    # New fields from preset-driven plan
    scene_type: str | None = None
    mood: str | None = None
    motion_intensity: float | None = None
    vfx_tags: list[str] = Field(default_factory=list)
    sfx_tags: list[str] = Field(default_factory=list)
    subtitle_mood: str | None = None


class VideoDirection(BaseModel):
    chapter: int
    total_duration_ms: int
    fps: int = 30
    width: int = 1920
    height: int = 1080
    scenes: list[SceneDirection]
    global_settings: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Video production job
# ---------------------------------------------------------------------------


class VideoJobPhase(str, Enum):
    queued = "queued"
    tts_generating = "tts_generating"
    directing = "directing"
    rendering = "rendering"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class VideoJobStatus(BaseModel):
    job_id: str
    phase: VideoJobPhase
    progress: int = 0
    detail: str = ""
    error: str | None = None
    download_url: str | None = None


class VideoProduceRequest(BaseModel):
    narration_path: str
    voice_key: str = "voice_default"
    speed: float = 1.15
    provider: str = "vieneu"
    style: str = "dark_xianxia_recap"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    direction_data: dict | None = None
    audio_paths: dict[int, str] | None = None


# ---------------------------------------------------------------------------
# Effect suggestion (Gemini)
# ---------------------------------------------------------------------------


class SceneEffectSuggestion(BaseModel):
    scene: int
    scene_type: str
    mood: str
    motion_preset: str
    motion_intensity: float
    transition: str
    transition_duration_ms: int
    vfx_tags: list[str] = Field(default_factory=list)
    sfx_tags: list[str] = Field(default_factory=list)
    subtitle_mood: str | None = None


class EffectSuggestionRequest(BaseModel):
    narration_path: str | None = None
    scenes: list[dict] | None = None  # Raw scenes if narration_path not yet saved
    style: str = "dark_xianxia_recap"


class EffectSuggestionResult(BaseModel):
    scenes: list[SceneEffectSuggestion]
