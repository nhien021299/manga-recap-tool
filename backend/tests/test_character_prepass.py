from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.core.config import Settings
from app.models.characters import (
    ChapterCharacterState,
    CharacterCandidateAssignment,
    CharacterCluster,
    CharacterCrop,
    CharacterPanelReference,
    PanelCharacterRef,
)
from app.services.characters.cluster import CharacterClusterer, ClusterInputCrop
from app.services.characters.detector import DetectedCrop
from app.services.characters.prepass import PREPASS_VERSION, CharacterPrepassService
from app.services.characters.quality import CharacterCropQuality
from app.services.characters.repository import CharacterStateRepository


TAM_MA_PANEL_DIR = Path(r"D:\Manhwa Recap\Tâm Ma\chapter 1 cropped")


def build_settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None).model_copy(
        update={
            "character_state_db_raw": str(tmp_path / ".temp" / "characters" / "state.sqlite3"),
            "character_cache_root_raw": str(tmp_path / ".temp" / "characters" / "cache"),
        }
    )


def draw_character_panel(path: Path, *, character: str, background: str, shift_x: int = 0, shift_y: int = 0) -> None:
    image = Image.new("L", (180, 260), color=248)
    draw = ImageDraw.Draw(image)

    if background == "rain":
        for index in range(0, 180, 18):
            draw.line((index, 0, index - 40, 260), fill=180, width=2)
    elif background == "grid":
        for index in range(0, 180, 20):
            draw.line((index, 0, index, 260), fill=210, width=1)
        for index in range(0, 260, 24):
            draw.line((0, index, 180, index), fill=210, width=1)
    elif background == "burst":
        for index in range(0, 180, 16):
            draw.line((90, 120, index, 0), fill=190, width=2)

    center_x = 92 + shift_x
    center_y = 112 + shift_y

    if character == "hero":
        draw.ellipse((center_x - 28, center_y - 42, center_x + 24, center_y + 12), fill=18)
        draw.rectangle((center_x - 20, center_y + 6, center_x + 12, center_y + 98), fill=28)
        draw.line((center_x - 20, center_y + 28, center_x - 56, center_y + 74), fill=24, width=10)
        draw.line((center_x + 12, center_y + 32, center_x + 46, center_y + 86), fill=24, width=10)
    elif character == "villain":
        draw.rectangle((center_x - 56, center_y - 30, center_x + 52, center_y + 6), fill=18)
        draw.rectangle((center_x - 10, center_y + 6, center_x + 12, center_y + 120), fill=38)
        draw.line((center_x - 48, center_y - 12, center_x - 76, center_y - 48), fill=28, width=10)
        draw.line((center_x + 48, center_y - 12, center_x + 74, center_y - 50), fill=28, width=10)
        draw.line((center_x - 6, center_y + 118, center_x - 32, center_y + 162), fill=28, width=10)
        draw.line((center_x + 8, center_y + 118, center_x + 40, center_y + 164), fill=28, width=10)
    elif character == "artifact":
        draw.ellipse((center_x - 42, center_y - 42, center_x + 42, center_y + 42), outline=24, width=14)
        draw.rectangle((center_x - 54, center_y + 56, center_x + 56, center_y + 94), fill=42)
        draw.line((center_x - 28, center_y - 28, center_x + 28, center_y + 28), fill=30, width=8)
        draw.line((center_x + 28, center_y - 28, center_x - 28, center_y + 28), fill=30, width=8)
    else:
        raise ValueError(f"Unsupported character '{character}'.")

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def draw_multi_character_panel(path: Path) -> None:
    image = Image.new("L", (240, 260), color=246)
    draw = ImageDraw.Draw(image)
    for index in range(0, 240, 24):
        draw.line((index, 0, index - 40, 260), fill=190, width=2)

    draw.ellipse((20, 44, 74, 98), fill=16)
    draw.rectangle((32, 94, 64, 188), fill=28)
    draw.line((32, 124, 8, 176), fill=24, width=10)
    draw.line((64, 126, 88, 182), fill=24, width=10)

    draw.ellipse((148, 66, 214, 132), outline=24, width=14)
    draw.rectangle((136, 146, 226, 186), fill=42)
    draw.line((156, 82, 202, 126), fill=30, width=8)
    draw.line((202, 82, 156, 126), fill=30, width=8)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def install_synthetic_face_detector(
    service: CharacterPrepassService,
    bboxes_by_panel: dict[str, tuple[int, int, int, int]],
) -> None:
    def detect(*, panel_id: str, order_index: int, path: Path):
        bbox = bboxes_by_panel[panel_id]
        return [
            DetectedCrop(
                panel_id=panel_id,
                order_index=order_index,
                bbox=bbox,
                detection_score=0.96,
                kind="head",
                detector_source="synthetic-test",
                detector_model="synthetic-head-v1",
                diagnostics={"synthetic": True},
            )
        ]

    service.detector.detect = detect  # type: ignore[method-assign]
    service.detector.version = "synthetic-head-detector-v1"


def make_detection_record(
    crop_id: str,
    *,
    bbox: tuple[int, int, int, int],
    kind: str,
    detector_source: str = "anime-face-detector",
    quality_score: float = 0.72,
    detection_score: float = 0.88,
) -> dict[str, object]:
    return {
        "crop_id": crop_id,
        "detection": DetectedCrop(
            panel_id="panel-dedup",
            order_index=0,
            bbox=bbox,
            detection_score=detection_score,
            kind=kind,  # type: ignore[arg-type]
            detector_source=detector_source,
            detector_model=detector_source,
            diagnostics={},
        ),
        "crop_kind": kind,
        "monster_like": False,
        "quality": CharacterCropQuality(score=quality_score, bucket="medium", diagnostics={"saturation": 0.35}),
        "crop_image": Image.new("RGB", (32, 32), color=(128, 128, 128)),
        "suppressed_by_crop_id": "",
        "suppression_reason": "",
        "duplicate_group_id": "",
    }


def test_prepass_groups_same_character_across_different_backgrounds(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)

    panel_specs = [
        ("panel-1", "hero", "rain", 0, 0),
        ("panel-2", "hero", "grid", 10, 4),
        ("panel-3", "hero", "burst", -8, 2),
        ("panel-4", "villain", "grid", 0, 0),
    ]
    panels: list[CharacterPanelReference] = []
    file_paths: list[Path] = []
    for order_index, (panel_id, character, background, shift_x, shift_y) in enumerate(panel_specs):
        path = tmp_path / f"{panel_id}.png"
        draw_character_panel(path, character=character, background=background, shift_x=shift_x, shift_y=shift_y)
        panels.append(CharacterPanelReference(panelId=panel_id, orderIndex=order_index))
        file_paths.append(path)

    install_synthetic_face_detector(
        service,
        {
            "panel-1": (54, 54, 78, 86),
            "panel-2": (64, 58, 78, 86),
            "panel-3": (46, 56, 78, 86),
            "panel-4": (34, 72, 118, 72),
        },
    )

    state = service.run(chapter_id="chapter-auto-group", panels=panels, file_paths=file_paths, force=True)

    assert state.prepassVersion == PREPASS_VERSION
    assert state.crops
    assert state.candidateAssignments
    assert len(state.clusters) >= 1
    largest_cluster = max(state.clusters, key=lambda cluster: cluster.occurrenceCount)
    assert largest_cluster.occurrenceCount >= 2
    assert {"panel-1", "panel-2"}.issubset(set(largest_cluster.samplePanelIds))

    refs_by_panel = {item.panelId: item for item in state.panelCharacterRefs}
    assert refs_by_panel["panel-1"].clusterIds == [largest_cluster.clusterId]
    assert refs_by_panel["panel-2"].clusterIds == [largest_cluster.clusterId]
    
    panel_1_candidates = [assignment for assignment in state.candidateAssignments if assignment.panelId == "panel-1"]
    hero_cluster_id = panel_1_candidates[0].clusterId
    assert panel_1_candidates[0].state == "auto_confirmed"
    
    panel_2_candidates = [assignment for assignment in state.candidateAssignments if assignment.panelId == "panel-2"]
    assert any(assignment.clusterId == hero_cluster_id and assignment.state == "auto_confirmed" for assignment in panel_2_candidates)
    
    panel_3_candidates = [assignment for assignment in state.candidateAssignments if assignment.panelId == "panel-3"]
    assert any(assignment.clusterId == hero_cluster_id and assignment.state == "auto_confirmed" for assignment in panel_3_candidates)
    assert refs_by_panel["panel-3"].clusterIds == [hero_cluster_id]


def test_prepass_keeps_visually_different_characters_separate(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)

    panel_specs = [
        ("panel-a", "hero", "rain", 0, 0),
        ("panel-b", "artifact", "rain", 0, 0),
        ("panel-c", "artifact", "grid", 8, 0),
    ]
    panels: list[CharacterPanelReference] = []
    file_paths: list[Path] = []
    for order_index, (panel_id, character, background, shift_x, shift_y) in enumerate(panel_specs):
        path = tmp_path / f"{panel_id}.png"
        draw_character_panel(path, character=character, background=background, shift_x=shift_x, shift_y=shift_y)
        panels.append(CharacterPanelReference(panelId=panel_id, orderIndex=order_index))
        file_paths.append(path)

    install_synthetic_face_detector(
        service,
        {
            "panel-a": (54, 54, 78, 86),
            "panel-b": (48, 62, 88, 88),
            "panel-c": (56, 62, 88, 88),
        },
    )

    state = service.run(chapter_id="chapter-separate", panels=panels, file_paths=file_paths, force=True)

    refs_by_panel = {item.panelId: item for item in state.panelCharacterRefs}
    assert refs_by_panel["panel-b"].clusterIds
    assert refs_by_panel["panel-c"].clusterIds

    panel_b_candidates = [assignment for assignment in state.candidateAssignments if assignment.panelId == "panel-b"]
    panel_c_candidates = [assignment for assignment in state.candidateAssignments if assignment.panelId == "panel-c"]
    
    assert panel_b_candidates
    assert panel_c_candidates
    
    artifact_cluster_id = panel_b_candidates[0].clusterId
    artifact_cluster = next(c for c in state.clusters if c.clusterId == artifact_cluster_id)
    anchor_panel_ids = {crop.panelId for crop in state.crops if crop.cropId in artifact_cluster.anchorCropIds}
    
    assert "panel-b" in anchor_panel_ids
    assert "panel-c" in anchor_panel_ids
    assert "panel-a" not in anchor_panel_ids
    assert artifact_cluster_id not in refs_by_panel["panel-a"].clusterIds


def test_prepass_recomputes_when_cached_state_uses_old_version(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)

    panel_specs = [
        ("panel-1", "hero", "rain", 0, 0),
        ("panel-2", "hero", "grid", 8, 2),
    ]
    panels: list[CharacterPanelReference] = []
    file_paths: list[Path] = []
    for order_index, (panel_id, character, background, shift_x, shift_y) in enumerate(panel_specs):
        path = tmp_path / f"{panel_id}.png"
        draw_character_panel(path, character=character, background=background, shift_x=shift_x, shift_y=shift_y)
        panels.append(CharacterPanelReference(panelId=panel_id, orderIndex=order_index))
        file_paths.append(path)

    chapter_content_hash = service._compute_content_hash(panels, file_paths)
    stale_state = ChapterCharacterState(
        chapterId="chapter-stale",
        chapterContentHash=chapter_content_hash,
        prepassVersion="heuristic-panel-v2",
        generatedAt="2026-04-24T00:00:00+00:00",
        updatedAt="2026-04-24T00:00:00+00:00",
        needsReview=True,
        clusters=[],
        crops=[],
        candidateAssignments=[],
        panelCharacterRefs=[PanelCharacterRef(panelId="panel-1", clusterIds=[], source="unknown", confidenceScore=0.0)],
        unresolvedPanelIds=["panel-1"],
        clusterDiagnostics={},
        diagnostics={},
    )
    repository.save(stale_state)

    cache_path = service._cache_path("chapter-stale", chapter_content_hash)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(stale_state.model_dump_json(indent=2), encoding="utf-8")

    state = service.run(chapter_id="chapter-stale", panels=panels, file_paths=file_paths, force=False)

    assert state.prepassVersion == PREPASS_VERSION
    assert state.diagnostics
    assert state.diagnostics["summary"]["panelCount"] == 2
    assert "pairs" in state.diagnostics


def test_prepass_force_bypasses_reusable_repository_state(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)

    path = tmp_path / "panel-force.png"
    draw_character_panel(path, character="hero", background="rain")
    panels = [CharacterPanelReference(panelId="panel-force", orderIndex=0)]

    first_state = service.run(chapter_id="chapter-force", panels=panels, file_paths=[path], force=True)
    assert first_state.diagnostics["panels"]["panel-force"]["detectorVersion"] != "force-detector-test"

    service.detector.version = "force-detector-test"
    next_state = service.run(chapter_id="chapter-force", panels=panels, file_paths=[path], force=True)

    assert next_state.diagnostics["panels"]["panel-force"]["detectorVersion"] == "force-detector-test"


def test_prepass_recomputes_when_cached_detector_version_changes(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)

    path = tmp_path / "panel-cache-version.png"
    draw_character_panel(path, character="hero", background="rain")
    panels = [CharacterPanelReference(panelId="panel-cache-version", orderIndex=0)]

    first_state = service.run(chapter_id="chapter-cache-version", panels=panels, file_paths=[path], force=True)
    assert first_state.diagnostics["summary"]["versions"]["detector"] != "detector-version-test"

    service.detector.version = "detector-version-test"
    next_state = service.run(chapter_id="chapter-cache-version", panels=panels, file_paths=[path], force=False)

    assert next_state.diagnostics["summary"]["versions"]["detector"] == "detector-version-test"
    assert next_state.diagnostics["panels"]["panel-cache-version"]["detectorVersion"] == "detector-version-test"


def test_prepass_marks_blank_panel_as_unresolved_unknown(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)

    blank_path = tmp_path / "blank.png"
    Image.new("L", (180, 260), color=255).save(blank_path, format="PNG")
    panels = [CharacterPanelReference(panelId="panel-blank", orderIndex=0)]

    state = service.run(chapter_id="chapter-blank", panels=panels, file_paths=[blank_path], force=True)

    assert state.crops == []
    assert state.panelCharacterRefs[0].clusterIds == []
    assert state.unresolvedPanelIds == ["panel-blank"]


def test_prepass_keeps_ambiguous_mixed_panel_unresolved(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)

    panel_specs = [
        ("panel-hero", "hero", "rain", 0, 0),
        ("panel-artifact", "artifact", "grid", 0, 0),
    ]
    panels: list[CharacterPanelReference] = []
    file_paths: list[Path] = []
    for order_index, (panel_id, character, background, shift_x, shift_y) in enumerate(panel_specs):
        path = tmp_path / f"{panel_id}.png"
        draw_character_panel(path, character=character, background=background, shift_x=shift_x, shift_y=shift_y)
        panels.append(CharacterPanelReference(panelId=panel_id, orderIndex=order_index))
        file_paths.append(path)

    mixed_path = tmp_path / "panel-mixed.png"
    draw_multi_character_panel(mixed_path)
    panels.append(CharacterPanelReference(panelId="panel-mixed", orderIndex=2))
    file_paths.append(mixed_path)

    state = service.run(chapter_id="chapter-multi", panels=panels, file_paths=file_paths, force=True)

    refs_by_panel = {item.panelId: item for item in state.panelCharacterRefs}
    assert refs_by_panel["panel-mixed"].clusterIds == []
    assert "panel-mixed" not in state.unresolvedPanelIds
    assert all(ref.source != "suggested" for ref in state.panelCharacterRefs)


def test_learned_embedder_fails_fast_without_learned_model(tmp_path: Path):
    settings = build_settings(tmp_path).model_copy(
        update={
            "character_embedder": "arcface-dino",
            "character_arcface_model_path": str(tmp_path / "missing-arcface.onnx"),
            "character_dino_model_path": str(tmp_path / "missing-dino"),
        }
    )
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)

    path = tmp_path / "panel.png"
    draw_character_panel(path, character="hero", background="rain")
    panels = [CharacterPanelReference(panelId="panel-1", orderIndex=0)]

    with pytest.raises(RuntimeError, match="no learned identity model"):
        service.run(chapter_id="chapter-learned-missing", panels=panels, file_paths=[path], force=True)


def test_learned_mode_rejects_handcrafted_auto_clusters():
    clusterer = CharacterClusterer(clusterer="hdbscan", min_cluster_size=2)
    vector = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
    crops = [
        ClusterInputCrop(
            crop_id="panel-1::crop::01",
            panel_id="panel-1",
            order_index=0,
            vector=vector,
            quality_bucket="good",
            crop_kind="face",
            embedding_provider="handcrafted",
            learned_mode=True,
        ),
        ClusterInputCrop(
            crop_id="panel-2::crop::01",
            panel_id="panel-2",
            order_index=1,
            vector=vector,
            quality_bucket="good",
            crop_kind="face",
            embedding_provider="handcrafted",
            learned_mode=True,
        ),
    ]

    clusters, assignments = clusterer.cluster(crops)

    assert clusters == []
    assert all(assignment.state == "unknown" for assignment in assignments)


def test_unknown_context_crops_do_not_make_panel_unresolved(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)
    panel = CharacterPanelReference(panelId="panel-context", orderIndex=0)
    crop = CharacterCrop(
        cropId="panel-context::crop::01",
        panelId="panel-context",
        orderIndex=0,
        bbox=[0, 0, 120, 160],
        kind="heuristic",
        assignmentState="unknown",
        diagnostics={"identityEligible": False, "identityRole": "context"},
    )
    ref = PanelCharacterRef(panelId="panel-context", clusterIds=[], source="unknown", confidenceScore=0.0)

    assert service._build_unresolved_panels(panels=[panel], crops=[crop], panel_refs=[ref]) == []


def test_duplicate_suppression_collapses_face_inside_head(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)
    records = [
        make_detection_record("panel::crop::01", bbox=(610, 193, 258, 335), kind="face"),
        make_detection_record("panel::crop::02", bbox=(417, 0, 523, 745), kind="head", quality_score=0.78),
    ]

    service._suppress_duplicate_records(records)

    face_record, head_record = records
    assert face_record["suppressed_by_crop_id"] == ""
    assert head_record["suppressed_by_crop_id"] == "panel::crop::01"
    assert head_record["suppression_reason"] == "face_inside_head"
    assert face_record["duplicate_group_id"] == head_record["duplicate_group_id"]


def test_duplicate_suppression_keeps_separated_people(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)
    records = [
        make_detection_record("panel::crop::01", bbox=(20, 30, 80, 100), kind="face"),
        make_detection_record("panel::crop::02", bbox=(180, 32, 82, 104), kind="face"),
    ]

    service._suppress_duplicate_records(records)

    assert all(record["suppressed_by_crop_id"] == "" for record in records)
    assert all(record["duplicate_group_id"] == "" for record in records)


def test_duplicate_suppression_makes_heuristic_container_context_only(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)
    records = [
        make_detection_record("panel::crop::01", bbox=(120, 90, 120, 150), kind="face"),
        make_detection_record(
            "panel::crop::02",
            bbox=(80, 40, 260, 330),
            kind="heuristic",
            detector_source="opencv-heuristic",
            quality_score=0.81,
            detection_score=0.54,
        ),
    ]

    service._suppress_duplicate_records(records)

    assert records[0]["suppressed_by_crop_id"] == ""
    assert records[1]["suppressed_by_crop_id"] == "panel::crop::01"
    assert records[1]["suppression_reason"] == "anime_or_identity_crop_over_heuristic"


def test_suppressed_identity_crop_does_not_make_panel_unresolved(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)
    panel = CharacterPanelReference(panelId="panel-suppressed", orderIndex=0)
    crop = CharacterCrop(
        cropId="panel-suppressed::crop::02",
        panelId="panel-suppressed",
        orderIndex=0,
        bbox=[417, 0, 523, 745],
        kind="head",
        assignmentState="unknown",
        diagnostics={"suppressedByCropId": "panel-suppressed::crop::01", "identityEligible": False},
    )
    ref = PanelCharacterRef(panelId="panel-suppressed", clusterIds=[], source="unknown", confidenceScore=0.0)

    assert not service._is_identity_relevant_crop(crop)
    assert service._build_unresolved_panels(panels=[panel], crops=[crop], panel_refs=[ref]) == []


def test_panel_refs_ignore_impure_or_low_confidence_auto_clusters(tmp_path: Path):
    settings = build_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)
    low_crop = CharacterCrop(
        cropId="panel-low::crop::01",
        panelId="panel-low",
        orderIndex=0,
        bbox=[0, 0, 80, 100],
        kind="face",
        assignedClusterId="char_low",
        assignmentState="auto_confirmed",
    )
    manual_crop = CharacterCrop(
        cropId="panel-manual::crop::01",
        panelId="panel-manual",
        orderIndex=1,
        bbox=[0, 0, 80, 100],
        kind="face",
        assignedClusterId="char_impure",
        assignmentState="manual",
    )
    clusters = [
        CharacterCluster(clusterId="char_low", chapterId="chapter", status="review_needed", reviewFlags=["low_confidence"]),
        CharacterCluster(clusterId="char_impure", chapterId="chapter", status="review_needed", reviewFlags=["impure_cluster"]),
    ]
    assignments = [
        CharacterCandidateAssignment(cropId=low_crop.cropId, panelId=low_crop.panelId, clusterId="char_low", rank=1, score=0.99, state="auto_confirmed"),
        CharacterCandidateAssignment(cropId=manual_crop.cropId, panelId=manual_crop.panelId, clusterId="char_impure", rank=1, score=1.0, state="manual"),
    ]

    refs = service._build_panel_refs(
        crops=[low_crop, manual_crop],
        clusters=clusters,
        candidate_assignments=assignments,
        panel_order={"panel-low": 0, "panel-manual": 1},
    )
    refs_by_panel = {ref.panelId: ref for ref in refs}

    assert refs_by_panel["panel-low"].clusterIds == []
    assert refs_by_panel["panel-manual"].clusterIds == ["char_impure"]


@pytest.mark.skipif(os.environ.get("RUN_TAM_MA_REGRESSION") != "1", reason="Local Tâm Ma regression is opt-in.")
@pytest.mark.skipif(not TAM_MA_PANEL_DIR.exists(), reason="Local Tâm Ma panel folder is unavailable.")
def test_tam_ma_learned_regression_with_local_chapter(tmp_path: Path):
    settings = build_settings(tmp_path).model_copy(
        update={
            "character_detector_mode": "hybrid",
            "character_anime_face_model_path": str((Path(__file__).resolve().parents[1] / ".models" / "anime-face" / "anime-face-detect.onnx").resolve()),
            "character_embedder": "arcface-dino",
            "character_dino_model_path": str((Path(__file__).resolve().parents[1] / ".models" / "dinov2").resolve()),
            "character_arcface_model_path": str((Path(__file__).resolve().parents[1] / ".models" / "arcface" / "arcface.onnx").resolve()),
            "character_embed_device": "cpu",
        }
    )
    repository = CharacterStateRepository(settings.character_state_db)
    service = CharacterPrepassService(settings, repository)
    panel_paths = sorted(TAM_MA_PANEL_DIR.glob("scene-*.png"))
    panels = [
        CharacterPanelReference(panelId=f"scene-{index + 1:03d}", orderIndex=index)
        for index, _path in enumerate(panel_paths)
    ]

    state = service.run(chapter_id="tam-ma-regression", panels=panels, file_paths=panel_paths, force=True)
    refs_by_panel = {ref.panelId: ref for ref in state.panelCharacterRefs}

    assert refs_by_panel["scene-001"].clusterIds == []
    assert all(crop.assignedClusterId is None for crop in state.crops if crop.panelId == "scene-001")
    assert any(crop.diagnostics.get("identityRole") == "fallback_head" for crop in state.crops if crop.panelId in {"scene-002", "scene-006"})
    assert any(crop.detectorSource == "opencv-heuristic" for crop in state.crops)
    assert any(crop.detectorSource == "anime-face-detector" for crop in state.crops)
    duplicate_failure_panels = {"scene-010", "scene-024", "scene-028", "scene-033", "scene-044", "scene-048"}
    suppressed_duplicates = [
        crop
        for crop in state.crops
        if crop.panelId in duplicate_failure_panels and crop.diagnostics.get("suppressedByCropId")
    ]
    assert suppressed_duplicates
    assert all(crop.assignedClusterId is None for crop in suppressed_duplicates)
