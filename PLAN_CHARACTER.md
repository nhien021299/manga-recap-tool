# Character System V2 - Saved WIP State

Updated on `2026-04-24`.

## Goal

Move the character system from panel-level heuristic grouping to a crop-level identity pipeline:

- detect multiple candidate crops per panel
- score crop quality
- embed usable crops
- cluster anchors conservatively
- review/override at crop level
- keep `panelCharacterRefs` stable for Script step

## What Is Already Implemented

### Backend schema and contracts

- `backend/app/models/characters.py`
  - added crop-level state:
    - `CharacterCrop`
    - `CharacterCandidateAssignment`
    - `ChapterCharacterState.crops`
    - `ChapterCharacterState.candidateAssignments`
    - `ChapterCharacterState.unresolvedPanelIds`
    - `ChapterCharacterState.clusterDiagnostics`
  - added `CharacterCluster.anchorCropIds`
  - added `CharacterCropMappingRequest`
  - bumped prepass version default to `character-crop-v2`

### Backend services

- New modules added:
  - `backend/app/services/characters/detector.py`
  - `backend/app/services/characters/quality.py`
  - `backend/app/services/characters/embedder.py`
  - `backend/app/services/characters/cluster.py`
- `backend/app/services/characters/prepass.py`
  - fully replaced old `heuristic-panel-v2` panel fingerprint logic
  - now orchestrates:
    - multi-crop detection
    - quality gate
    - embedding cache
    - agglomerative clustering
    - crop preview generation
    - panel ref aggregation
- `backend/app/services/characters/cluster.py`
  - now runs singleton-anchor refinement after initial agglomerative clustering
  - uses the same centroid/anchor blend for refinement and medium-crop candidate scoring
  - blocks same-panel collapse when assigning non-anchor crops to clusters
- `backend/app/services/characters/review_state.py`
  - updated to work with crop-level assignments
  - supports:
    - manual cluster creation from crop(s)
    - rename/lock
    - merge
    - panel-level override
    - crop-level override

### Backend routes

- `backend/app/routes/characters.py`
  - added `POST /api/v1/characters/crop-mapping`
  - existing routes still preserved

### Frontend

- `web-app/src/shared/types/index.ts`
  - updated for crop-level character state
- `web-app/src/features/characters/api.ts`
  - added crop-mapping client call
  - manual cluster payload now supports `cropIds`
- `web-app/src/features/characters/components/StepCharacters.tsx`
  - rewritten around crop-level review
  - cluster cards now render crop thumbnails from `anchorCropIds`
  - panel inspector now shows detected crops and top candidates
  - quick panel override still exists

## Validation Status

### Passing

- `pytest backend/tests/test_routes.py -q`
- `pytest backend/tests/test_character_prepass.py -q`
- `npm run build:web`

### Current test shape

- Smoke and route tests were updated to the new schema.
- Mixed-panel acceptance is now active and passing:
  - `test_prepass_can_assign_multiple_clusters_to_same_panel`

## Recently Fixed Gap

### Mixed-panel refinement

Previous failure mode:

- when one panel contains multiple detected crops, one crop can still become a new singleton cluster instead of reattaching to an existing chapter cluster
- this leaves:
  - a ghost single-panel cluster
  - weaker `top1 - top2` margin for the other crop in the same panel
  - `panelCharacterRefs` with only one confirmed cluster instead of two

Current behavior:

- singleton anchors are rescored against external clusters after initial clustering
- same-panel collapse is blocked during both refinement and non-anchor candidate assignment
- the mixed-panel test now verifies at least two confirmed cluster ids for the same panel

## Next Step To Continue

1. Run frontend build and focused end-to-end manual checks against real extracted chapters.
2. Surface cluster/crop diagnostics in `StepCharacters` so users can inspect why a crop was confirmed, suggested, or blocked.
3. Tune `SINGLETON_ATTACH_SIMILARITY_THRESHOLD`, `SINGLETON_ATTACH_MARGIN_THRESHOLD`, and medium-crop thresholds on real chapter data without lowering the split-over-merge posture.

## Suggested Threshold Work

Current clustering is intentionally conservative:

- `ANCHOR_DISTANCE_THRESHOLD = 0.08`
- `SINGLETON_ATTACH_SIMILARITY_THRESHOLD = 0.92`
- `SINGLETON_ATTACH_MARGIN_THRESHOLD = 0.08`
- merge warning threshold raised to `0.92`

When continuing:

- keep `split > merge`
- prefer unresolved/suggested over destructive merge
- do not lower margin rules without checking mixed-panel and visually similar character chapters

## Files Changed In This WIP

- `backend/app/models/characters.py`
- `backend/app/routes/characters.py`
- `backend/app/services/characters/prepass.py`
- `backend/app/services/characters/review_state.py`
- `backend/app/services/characters/detector.py`
- `backend/app/services/characters/quality.py`
- `backend/app/services/characters/embedder.py`
- `backend/app/services/characters/cluster.py`
- `backend/tests/test_character_prepass.py`
- `backend/tests/test_routes.py`
- `web-app/src/features/characters/api.ts`
- `web-app/src/features/characters/components/StepCharacters.tsx`
- `web-app/src/shared/types/index.ts`

## Notes

- The old plan text was replaced with this concrete WIP handoff because the repository has already moved beyond planning and now needs a continuation note.
- `ROADMAP.md` should be kept aligned with this file; do not mark Character System V2 as done yet.
