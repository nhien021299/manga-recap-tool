from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.core.config import Settings
from app.models.characters import ChapterCharacterState, CharacterPanelReference, PanelCharacterRef
from app.services.characters.prepass import PREPASS_VERSION, CharacterPrepassService
from app.services.characters.repository import CharacterStateRepository


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

    state = service.run(chapter_id="chapter-auto-group", panels=panels, file_paths=file_paths, force=True)

    assert state.prepassVersion == PREPASS_VERSION
    assert state.crops
    assert state.candidateAssignments
    assert len(state.clusters) >= 1
    largest_cluster = max(state.clusters, key=lambda cluster: cluster.occurrenceCount)
    assert largest_cluster.occurrenceCount >= 2
    assert {"panel-1", "panel-2"}.issubset(set(largest_cluster.samplePanelIds))

    refs_by_panel = {item.panelId: item for item in state.panelCharacterRefs}
    hero_cluster_id = refs_by_panel["panel-1"].clusterIds[0]
    assert refs_by_panel["panel-2"].clusterIds == [hero_cluster_id]
    panel_3_candidates = [assignment for assignment in state.candidateAssignments if assignment.panelId == "panel-3"]
    assert any(assignment.clusterId == hero_cluster_id and assignment.state == "suggested" for assignment in panel_3_candidates)
    assert refs_by_panel["panel-3"].clusterIds == []


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

    state = service.run(chapter_id="chapter-separate", panels=panels, file_paths=file_paths, force=True)

    refs_by_panel = {item.panelId: item for item in state.panelCharacterRefs}
    if refs_by_panel["panel-a"].clusterIds:
        assert refs_by_panel["panel-b"].clusterIds != refs_by_panel["panel-a"].clusterIds
    assert refs_by_panel["panel-b"].clusterIds
    assert refs_by_panel["panel-c"].clusterIds == refs_by_panel["panel-b"].clusterIds


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


def test_prepass_can_assign_multiple_clusters_to_same_panel(tmp_path: Path):
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
    assert "panel-mixed" in state.unresolvedPanelIds
    assert all(ref.source != "suggested" for ref in state.panelCharacterRefs)
