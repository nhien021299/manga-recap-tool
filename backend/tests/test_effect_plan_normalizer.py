import json

from app.models.video import (
    BatchTtsResult,
    NarrationPackage,
    SceneInput,
    SceneTtsResult,
)
from app.services.effect_plan_normalizer import EffectPlanNormalizer


def _tts_result() -> BatchTtsResult:
    return BatchTtsResult(
        job_id="test",
        total_scenes=1,
        total_audio_duration_ms=3000,
        scene_results=[
            SceneTtsResult(
                scene=1,
                title="Cave",
                audio_path="scene_01.wav",
                audio_duration_ms=3000,
                target_duration_ms=4000,
                narration="",
            )
        ],
    )


def test_normalize_plan_strips_orphan_speaker_attribution_from_narration_overlay():
    package = NarrationPackage(
        project="manga-recap",
        chapter=1,
        scenes=[
            SceneInput(
                scene=1,
                title="Cave",
                duration_seconds=4,
                narration="Rồi hắn khựng lại. Trong tay Tiểu Hồng có một mảnh đá đen nhánh. Tô Minh nói. Người cầm cái gì đó?",
                dialogue="Người cầm cái gì đó?",
                dialogue_speaker="Tô Minh",
            )
        ],
    )
    raw_plan = json.dumps(
        {
            "items": [
                [1, "dialogue", "tense", "push_in_center", 0.7, "crossfade", 500, [], "neutral"]
            ]
        }
    )

    direction = EffectPlanNormalizer.normalize_plan(
        raw_plan,
        package,
        _tts_result(),
        width=1080,
        height=1920,
        fps=30,
    )

    overlays = direction.scenes[0].text_overlays
    assert overlays[0].style == "subtitle"
    assert overlays[0].text == "Rồi hắn khựng lại. Trong tay Tiểu Hồng có một mảnh đá đen nhánh"
    assert overlays[1].style == "dialogue_bubble"
    assert overlays[1].text == "Người cầm cái gì đó?"


def test_default_scene_direction_uses_same_dialogue_dedupe():
    scene = SceneInput(
        scene=1,
        title="Cave",
        duration_seconds=4,
        narration="Tô Minh nói: Người cầm cái gì đó?",
        dialogue="Người cầm cái gì đó?",
        dialogue_speaker="Tô Minh",
    )

    direction = EffectPlanNormalizer._default_scene_direction(scene, _tts_result().scene_results[0])

    assert direction.text_overlays == []
