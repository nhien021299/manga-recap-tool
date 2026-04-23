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
- Step Script runs through backend Gemini
- Step Voice runs only through backend routes
- Timeline state lives in frontend store
- Official MP4 export now runs through backend async native `ffmpeg`
- Browser FFmpeg export remains as fallback/preview with deterministic motion

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

## Active API Surface

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

1. One TTS path only should remain active: `vieneu + voice_default`.
2. `voice_default` must continue to be treated as a cached preset, not a per-request clone.
3. Backend-native render is now the official export engine.
4. Browser render remains useful as fallback/preview, but stays the heavier path for long timelines.
5. Frontend workflow guidance and design guidance are now aligned more closely with the live workstation-style UI.
6. Timeline editing is now consolidated around the Timeline & Render step, with reset/duplicate/remove clip actions and bulk stale-audio regeneration.

## Next Actions

1. Continue narration polish and usability improvements on top of the now-stable timeline editor and export architecture.
2. Keep README, ROADMAP, setup scripts, and active env defaults synchronized whenever TTS or export decisions change.
3. Decide later whether backend-native render should adopt the same motion spec as browser fallback for parity.
4. Monitor render-job stability, ffmpeg availability, and TTL cleanup behavior in longer real-world exports.

## Open Risks

- Browser-side FFmpeg remains memory-heavy for long timelines even as fallback.
- Backend-native export depends on a valid local `ffmpeg` binary path and host runtime availability.
- Browser and backend render paths now share plan structure, but visual parity is not yet exact because motion is currently implemented only in browser fallback.
- Rebuilding `voice_default` from a different reference source will change the production narration voice globally.
- VieNeu standard mode still depends on a complete Python runtime with `torch`, `torchaudio`, `transformers`, `neucodec`, and `vieneu`.
