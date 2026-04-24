# Manga Recap Tool - Executive Roadmap

## Current Product State

Repo is now an active frontend-backend creator tool:

```text
manga-recap-tool/
|- web-app/
|- backend/
|- ai/
|- PLAN.md
|- PLAN_EXPORT.md
`- ROADMAP.md
```

- `web-app/`: upload, extract, script, voice, timeline, and export UI
- `backend/`: FastAPI service for Gemini script generation and backend-owned VieNeu TTS
- `PLAN.md`: approved direction for native backend render jobs with browser fallback
- `PLAN_EXPORT.md`: approved direction for cinematic Ken Burns / keyframed browser export motion

Active architecture as of `2026-04-22`:

- FE-BE structure is the active product shape
- Upload and extraction stay browser-side
- Step Characters now exists between Extract and Script
- Step Script runs through backend Gemini
- Step Voice runs only through backend routes
- Timeline state lives in frontend store
- Official MP4 export now runs through backend async native `ffmpeg`
- Browser FFmpeg export remains as fallback/preview with deterministic motion

## Checkpoint: Character System 4-Phase Upgrade (2026-04-24)

### Phase 1: Block Heuristic Auto Cluster ✅ (Target: 6/10)

- Modified clustering policy so `heuristic` crops never create `auto_confirmed` assignments.
- Heuristic-only clusters stay as `suggested` or `unknown` and require manual review.
- Script context no longer receives any cluster based solely on heuristic signals.
- Tests updated to verify `suggested` candidates and explicit anchors.

### Phase 2: Anime Face/Head as Primary Identity ✅ (Target: 7.5/10)

- Added `warmup_test()` method to `CharacterCropDetector` for verifying anime face/head provider availability.
- Added `runtime_diagnostics()` to expose provider loaded/error, device, model path, and per-kind detection counts.
- Detector now tracks `_total_face_count`, `_total_head_count`, `_total_heuristic_count`, `_total_object_count`.
- `DETECTOR_VERSION` bumped to `hybrid-detector-v4`.
- `PREPASS_VERSION` bumped to `character-hybrid-v4`.
- Prepass diagnostics now use the detector's `runtime_diagnostics()` for full observability.
- Face/head crops remain the only kind eligible for `auto_confirmed` identity anchoring.
- If anime provider fails, system falls back to OpenCV heuristic with diagnostics explaining the reason.

### Phase 3: Cast-Anchor Propagation ✅ (Target: 8.5/10)

- Built anchor bank from locked clusters' face/head embedding vectors loaded from cache.
- On rerun, new unassigned face/head crops are scored against the anchor bank.
- If similarity ≥ 0.88 with margin ≥ 0.10, the crop is `auto_confirmed` via anchor propagation.
- If two locked anchors conflict (both ≥ 0.88, margin < 0.10), the crop is set to `suggested` with `anchor_conflict` review flag.
- Split constraints collected from `splitFromClusterId` diagnostics prevent re-merge of previously split clusters.
- Manual panel overrides and locked cluster names are preserved through reruns.
- Panel refs updated for propagated crops.

### Phase 4: DINOv2 Learned Embedding ✅ (Target: 9/10)

- Added hybrid `CharacterCropEmbedder` with DINOv2 support.
- `EMBEDDER_VERSION` bumped to `crop-embedding-v2`.
- `CLUSTER_VERSION` bumped to `hybrid-hdbscan-v4`.
- New config settings added:
  - `AI_BACKEND_CHARACTER_EMBEDDER` (default: `handcrafted`)
  - `AI_BACKEND_CHARACTER_DINO_MODEL_PATH` (default: empty)
  - `AI_BACKEND_CHARACTER_EMBED_DEVICE` (default: `auto`)
- When DINOv2 model path exists locally:
  - DINOv2 embedding is the primary signal (weight 2.8x)
  - Handcrafted descriptor is supplementary (weight 0.6x)
  - Combined into a single hybrid normalized vector
- When DINOv2 model is missing, system falls back to handcrafted-only with diagnostics.
- Cache key includes: embedder provider, DINO model hash, device, crop kind, detector version/config.
- Added `embed_batch()` for batch DINOv2 inference to avoid per-crop model calls.
- Added `runtime_diagnostics()` to the embedder for observability.
- Model never downloads at runtime — only uses local file.

### Current Achievement Assessment

| Phase | Target | Status | Notes |
| --- | --- | --- | --- |
| Phase 1 | 6/10 | ✅ Fully met | Heuristic auto-confirm blocked, script context clean. |
| Phase 2 | 7.5/10 | ✅ Code complete | Anime face/head is primary identity path with runtime diagnostics. Warmup test available. Without anime-face-detector dependency installed, system operates at Phase 1 quality (~6/10). |
| Phase 3 | 8.5/10 | ✅ Code complete | Anchor bank propagation, split protection, and conflict detection implemented. Effective only when previous locked state exists with cached embeddings. |
| Phase 4 | 9/10 | ✅ Code complete | DINOv2 hybrid embedding ready. Requires local DINOv2 .pt model file to activate. Without it, falls back to handcrafted (~Phase 2/3 quality). |

**Current effective quality: ~6/10** (Phase 1 fully active). Phases 2–4 are code-complete but require runtime dependencies to reach their target scores:
- Phase 2 needs `anime-face-detector` Python package installed
- Phase 3 needs previous locked state with cached embeddings
- Phase 4 needs DINOv2 `.pt` model file at the configured path

## Checkpoint: Character System V2 WIP Save (2026-04-24)

This is the saved handoff state for the crop-level rewrite. Character V2 is **not finished yet** and should not be treated as production-complete.

### Already implemented

- Backend character state moved from panel-only grouping toward crop-level review data.
- New backend modules added for the V2 pipeline:
  - `detector.py`
  - `quality.py`
  - `embedder.py`
  - `cluster.py`
- `prepass.py` was rewritten to orchestrate:
  - multi-crop detection
  - crop quality scoring
  - embedding cache
  - agglomerative clustering
  - panel-ref aggregation
- Review state now supports crop-level manual assignment through:
  - `POST /api/v1/characters/crop-mapping`
- Frontend `StepCharacters` was rewritten around crop previews and crop candidate review instead of full-panel-only merge review.

### Current validation snapshot

- Passing:
  - `pytest backend/tests/test_routes.py -q`
  - `pytest backend/tests/test_character_prepass.py -q`
  - `npm run build:web`

### Latest refinement

- `backend/app/services/characters/cluster.py` now includes a singleton-anchor refinement pass.
- Non-anchor crop candidate scoring now rejects same-panel cluster collapse, so separate crops in one mixed panel can confirm separate `panelCharacterRefs`.
- Prepass cache version was bumped to `character-crop-v2` and cluster version to `crop-cluster-v2` so older crop-level results are recomputed.

### Main unfinished item

- Character V2 still needs real-chapter threshold tuning and UI diagnostics polish before it should be treated as production-complete.

### Source of truth for continuation

- Continue from [PLAN_CHARACTER.md](./PLAN_CHARACTER.md)

## Checkpoint: Character System Integration (2026-04-24)

### Completed

- Integrated a dedicated character review step into the main pipeline:
  - `Extract -> Characters -> Script -> Voice -> Render`
- Added backend-owned character prepass and review state handling:
  - cluster generation
  - rename / merge / panel mapping actions
  - script-context generation for downstream prompt enforcement
- Added active character API surface:
  - `POST /api/v1/characters/prepass`
  - `GET /api/v1/characters/review`
  - `POST /api/v1/characters/review/rename`
  - `POST /api/v1/characters/review/merge`
  - `POST /api/v1/characters/review/panel-mapping`
  - `POST /api/v1/characters/review/create-cluster`
  - `POST /api/v1/characters/review/status`
  - `GET /api/v1/characters/script-context`
- Added frontend character workflow and storage wiring:
  - new `StepCharacters`
  - chapter-scoped prepass loading
  - character review state persisted in frontend store
  - script request now forwards `characterContext`
- Updated script generation contract so locked or reviewed character names are enforced through backend Gemini prompt context.
- Moved the selected panel preview to the left column under `Character List` to keep review flow tighter and reduce inspection friction.

### Prepass Evolution

- Initial prepass was intentionally conservative and favored `unknown` over risky merges.
- Prepass was then upgraded to a more proactive heuristic clusterer:
  - pairwise match scoring
  - multi-region perceptual hashes
  - shape profile comparison
  - Hu moments
  - foreground bbox and center-of-mass features
  - orientation histogram comparison
  - graph connected-components clustering
  - singleton attach for near-miss panels
- Current backend prepass version is:
  - `character-crop-v2`

### Diagnostics And Observability

- Added diagnostics payloads to character state so prepass decisions are inspectable:
  - `state.diagnostics.summary`
  - `cluster.diagnostics`
  - `panelCharacterRef.diagnostics`
  - `crop.diagnostics`
  - `candidateAssignment.diagnostics`
- Diagnostics now expose:
  - panel and cluster counts
  - auto-assigned vs unknown counts
  - threshold values
  - crop detection and quality metadata
  - candidate cluster scores
  - singleton refinement decisions

### Cache / Stale State Fix

- Fixed a real backend bug where `POST /api/v1/characters/prepass` could return stale cached state even after prepass logic changed.
- Root cause:
  - cache reuse previously depended only on `chapterContentHash`
  - old state with the same chapter content but older `prepassVersion` or missing diagnostics was still treated as valid
- Current invalidation rule now requires:
  - matching `chapterContentHash`
  - matching `prepassVersion`
  - non-empty diagnostics payload
- This prevents the frontend from silently receiving old prepass results after backend upgrades.

### Verification

- Backend tests passed after character-system work and stale-cache invalidation:
  - `python -m pytest tests`
  - `python -m pytest backend/tests/test_character_prepass.py backend/tests/test_routes.py`
- Frontend build passed after character workflow integration:
  - `npm --prefix web-app run build`
- Frontend lint passed with only pre-existing unrelated warnings in `StepVoice.tsx`.

## Checkpoint: TTS Runtime Hardening (2026-04-22)

### Completed

- Standardized production TTS on one path only:
  - provider: `vieneu`
  - model: `pnnbao-ump/VieNeu-TTS-0.3B`
  - mode: `standard`
  - canonical voice key: `voice_default`
- Confirmed runtime uses cached preset data from:
  - `backend/.models/vieneu-voices/voices.json`
- Confirmed runtime does not re-encode reference wav/txt on each request.
- Added preset build tooling:
  - [backend/scripts/build_voice_default_preset.py](./backend/scripts/build_voice_default_preset.py)
- Fixed missing dependency/runtime visibility issues around the dedicated VieNeu venv.
- Added more actionable backend errors for missing Python dependencies.
- Added backend logging for TTS generation:
  - `voiceKey`
  - resolved voice key
  - text length
  - elapsed time per clip
- Changed `GET /api/v1/voice/options` so it no longer loads and warms the VieNeu model.
- Removed legacy default handling around `voice_2_clone` and F5-related env/config assumptions from the active path.
- Set production temperature baseline to:
  - `AI_BACKEND_TTS_VIENEU_TEMPERATURE=0.7`

### Product Behavior Now Locked

- Opening or reloading the Voice step must not trigger model warmup.
- Only explicit user generation should load the model and synthesize clips.
- Restarting the backend will require model load + warmup again in RAM, but should reuse local cached weights instead of redownloading.

## Checkpoint: Legacy Local-AI and OCR Cleanup (2026-04-23)

### Completed

- **Standardized on Vision-Only Gemini**: Completely removed the inactive local-AI flows (Ollama text, Ollama vision, Llama.cpp) and OCR logic from the codebase.
- **Removed OCR Dependencies**: Uninstalled and removed `paddleocr` and `paddlepaddle` from `requirements.txt`.
- **Deleted Legacy Providers and Services**:
  - Removed `ollama_text.py`, `ollama_vision.py`, `llama_cpp_text.py`.
  - Deleted the entire `backend/app/providers/ocr/` directory.
  - Removed unused fallback logic (`llm_service.py`, `json_retry.py`).
- **Pruned Domain Models and API Interfaces**:
  - Cleaned `domain.py` by removing dead models (`OCRLine`, `OCRResult`, `VisionCaptionRaw`, etc.).
  - Stripped out legacy metrics (`ocrMs`, `mergeMs`, `identityOcrMs`) from both the backend `Metrics` model and frontend TypeScript definitions (`StepScript.tsx`, `index.ts`).
  - Removed `ProvidersResponse` and the `/system/providers` route.
- **Cleaned Configuration**:
  - Removed ~15 obsolete local-AI settings (chunk sizes, token limits, base URLs) from `.env`, `.env.example`, and `config.py`.
- **Refined Tests and Documentation**:
  - Fixed test assertions in `test_gemini_script_service.py` to match the cleaned vision-only identity fallback paths.
  - Updated Agent guides (`AGENTS.md`, `BACKEND-AGENTS.md`, etc.) to remove all mentions of legacy OCR and local LLM routing.
  - Deleted obsolete local-AI benchmarks (`vision-eval.md`).

## Checkpoint: Render And Export (2026-04-22)

### Completed Or Confirmed

- Browser export path is active and can produce a final MP4 from the timeline.
- FFmpeg core is bundled locally instead of fetched from CDN.
- Browser render now surfaces FFmpeg failures with better error detail instead of only `Render failed`.
- Render cleanup now deletes temporary clip files after each segment to reduce WASM FS pressure.
- Official export now runs through backend render jobs with native `ffmpeg`.
- Frontend now uploads one self-contained render payload to backend per export request.
- Backend render jobs now support:
  - progress phases
  - result download
  - cancellation
  - ephemeral result retention with TTL cleanup
- Backend render API is now active:
  - `POST /api/v1/render/jobs`
  - `GET /api/v1/render/jobs/{job_id}`
  - `GET /api/v1/render/jobs/{job_id}/result`
  - `POST /api/v1/render/jobs/{job_id}/cancel`
- Frontend render step now uses backend export as primary path.
- Browser fallback export now uses deterministic keyframed panel motion instead of single static frame per clip.
- Render plan now carries motion metadata and stable file-key mapping so backend and browser paths share one source of truth.
- Browser fallback progress now exposes clip animation/encode phases instead of one generic export state.
- Voice sample static serving was fixed on the backend.
- Voice sample assets now return a cross-origin policy compatible with frontend playback/preview.
- `206 Partial Content` on sample WAV requests is expected and valid for browser audio streaming.
- Frontend now shows per-clip voice generation progress instead of only a generic loading state.
- Frontend agent guidance was refreshed to reflect the real product shape:
  - browser-first for ingest/extract/edit
  - backend-assisted for AI generation and TTS
  - render/export-aware frontend architecture
- A dedicated render/export rule section now exists in:
  - [web-app/WEB-AGENTS.md](./web-app/WEB-AGENTS.md)
- Stale F5 setup references were removed from:
  - [setup.ps1](./setup.ps1)
  - [setup.sh](./setup.sh)

### Implemented From Approved Plans

#### 1. Official Export Architecture

Source of truth:
- [PLAN.md](./PLAN.md)

Implemented:
- official MP4 export moved to backend async render jobs using native `ffmpeg`
- browser render kept as fallback/preview only
- frontend sends one self-contained render payload to backend
- export flow exposes explicit progress, result preview/download, and cancel flow

#### 2. Cinematic Browser Motion Set

Source of truth:
- [PLAN_EXPORT.md](./PLAN_EXPORT.md)

Implemented:
- browser export upgraded from static frames to deterministic keyframed motion
- style target stays controlled and recap-oriented
- hard cuts between clips remain in v1
- no B-roll
- no subtitle animation
- motion metadata stays reusable at render-plan level

## Current Milestones

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | Done | FE-BE product structure is stable. |
| M1 Extract | Done | Browser-side upload and extraction are active. |
| M2 Script | Done | Backend Gemini route is the production script path. |
| M3 Voice | Done | Production TTS is standardized on `VieNeu-TTS-0.3B` with cached preset `voice_default`. |
| M4 Timeline | Done | Timeline editing now owns narration edits, clip actions, and export contract state from the frontend store. |
| M5 Browser Export | Done | Browser export remains available as fallback with deterministic keyframed motion. |
| M6 Native Export | Done | Backend async render jobs with native `ffmpeg` are now the official export path. |
| M7 Motion Polish | Done | Browser fallback now ships cinematic panel motion with hard cuts. |
| M8 Character System | Code Complete | All 4 phases implemented: heuristic block, anime face/head identity, cast-anchor propagation, DINOv2 hybrid embedding. Effective runtime quality depends on available dependencies (~6/10 baseline, up to 9/10 with full stack). |

## Active API Surface

- `POST /api/v1/characters/prepass`
- `GET /api/v1/characters/review`
- `POST /api/v1/characters/review/rename`
- `POST /api/v1/characters/review/merge`
- `POST /api/v1/characters/review/panel-mapping`
- `POST /api/v1/characters/review/create-cluster`
- `POST /api/v1/characters/review/status`
- `GET /api/v1/characters/script-context`
- `POST /api/v1/script/generate`
- `GET /api/v1/voice/options`
- `POST /api/v1/voice/generate`
- `GET /api/v1/system/tts`
- `POST /api/v1/render/jobs`
- `GET /api/v1/render/jobs/{job_id}`
- `GET /api/v1/render/jobs/{job_id}/result`
- `POST /api/v1/render/jobs/{job_id}/cancel`

## Agent Workflow And Rule Audit

### What Still Fits

- Root router in [AGENTS.md](./AGENTS.md) still fits the repo well:
  - frontend
  - backend
  - full-stack routing
- Backend guide in [backend/BACKEND-AGENTS.md](./backend/BACKEND-AGENTS.md) still fits:
  - API-first backend
  - service-layer orchestration
  - config/logging discipline
  - queue/cancellation guidance
- Shared project rules in [web-app/ai/project-rules.md](./web-app/ai/project-rules.md) still fit:
  - separation of UI and orchestration
  - explicit state handling
  - memory-safe processing

### Recently Updated

- [web-app/ai/design-rules.md](./web-app/ai/design-rules.md) was refreshed to describe the live workstation-style UI more accurately:
  - premium dark creator tool
  - denser control surfaces
  - modular workstation layout
  - restrained glow and glass usage

### Ongoing Documentation Rule

1. Keep setup guidance and root docs aligned with:
   - VieNeu-only production TTS
   - backend-native official export
   - browser fallback render behavior

## Current Product Conclusions

1. Character review is now a first-class step between extraction and script generation.
2. Backend prepass should prefer helping the user by clustering aggressively enough to be useful, while preserving manual override as the final source of truth.
3. Character naming consistency now depends on backend-supplied script context, not prompt luck alone.
4. Cache invalidation for character prepass must stay version-aware to avoid stale UI state.
5. One TTS path only should remain active: `vieneu + voice_default`.
6. `voice_default` must continue to be treated as a cached preset, not a per-request clone.
7. Backend-native render is now the official export engine.
8. Browser render remains useful as fallback/preview, but stays the heavier path for long timelines.
9. Frontend workflow guidance and design guidance are now aligned more closely with the live workstation-style UI.
10. Timeline editing is now consolidated around the Timeline & Render step, with reset/duplicate/remove clip actions and bulk stale-audio regeneration.

## Next Actions

1. Surface character diagnostics directly in the UI so users can see why panels were grouped or left unknown.
2. Continue tuning character prepass thresholds on real chapter data to improve grouping recall without introducing destructive merges.
3. Continue narration polish and usability improvements on top of the now-stable timeline editor and export architecture.
4. Keep README, ROADMAP, setup scripts, and active env defaults synchronized whenever TTS, character-system, or export decisions change.
5. Decide later whether backend-native render should adopt the same motion spec as browser fallback for parity.
6. Monitor render-job stability, ffmpeg availability, and TTL cleanup behavior in longer real-world exports.

## Open Risks

- Heuristic character grouping is stronger now, but still depends on panel crops rather than a learned identity embedding model.
- More aggressive auto-grouping increases usefulness, but also increases the risk of false merges on visually similar silhouettes.
- Diagnostics exist in API payloads, but are not yet surfaced clearly in the frontend review UI.
- Character review state correctness depends on keeping `chapterId`, extracted panel order, and prepass cache invalidation aligned.
- Browser-side FFmpeg remains memory-heavy for long timelines even as fallback.
- Backend-native export depends on a valid local `ffmpeg` binary path and host runtime availability.
- Browser and backend render paths now share plan structure, but visual parity is not yet exact because motion is currently implemented only in browser fallback.
- Rebuilding `voice_default` from a different reference source will change the production narration voice globally.
- VieNeu standard mode still depends on a complete Python runtime with `torch`, `torchaudio`, `transformers`, `neucodec`, and `vieneu`.
