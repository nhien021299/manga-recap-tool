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
- Render currently ships through browser-side FFmpeg
- Native backend render is the approved next-step export architecture

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

## Checkpoint: Render And Export (2026-04-22)

### Completed Or Confirmed

- Browser export path is active and can produce a final MP4 from the timeline.
- FFmpeg core is bundled locally instead of fetched from CDN.
- Browser render now surfaces FFmpeg failures with better error detail instead of only `Render failed`.
- Render cleanup now deletes temporary clip files after each segment to reduce WASM FS pressure.
- Voice sample static serving was fixed on the backend.
- Voice sample assets now return a cross-origin policy compatible with frontend playback/preview.
- `206 Partial Content` on sample WAV requests is expected and valid for browser audio streaming.
- Frontend now shows per-clip voice generation progress instead of only a generic loading state.

### Approved Next Plans

#### 1. Official Export Architecture

Source of truth:
- [PLAN.md](./PLAN.md)

Approved direction:
- move official MP4 export to backend async render jobs using native `ffmpeg`
- keep browser render as fallback or preview only
- send one self-contained render payload from frontend to backend
- expose explicit render progress, result download, and cancel flow

#### 2. Cinematic Browser Motion Set

Source of truth:
- [PLAN_EXPORT.md](./PLAN_EXPORT.md)

Approved direction:
- upgrade browser export from static frames to deterministic keyframed motion
- style target: manga recap / review, epic but controlled
- keep hard cuts between clips in v1
- no B-roll
- no subtitle animation
- motion spec should stay reusable later when the backend native renderer takes over

## Current Milestones

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | Done | FE-BE product structure is stable. |
| M1 Extract | Done | Browser-side upload and extraction are active. |
| M2 Script | Done | Backend Gemini route is the production script path. |
| M3 Voice | Done | Production TTS is standardized on `VieNeu-TTS-0.3B` with cached preset `voice_default`. |
| M4 Timeline | In Progress | Timeline editing, clip ordering, and narration polish remain active. |
| M5 Browser Export | In Progress | Browser FFmpeg export exists but is still too heavy for official final export. |
| M6 Native Export | Planned | Backend async render jobs with native `ffmpeg` are the approved official export path. |
| M7 Motion Polish | Planned | Ken Burns / keyframed panel motion is approved for the browser export path first. |

## Active API Surface

- `POST /api/v1/script/generate`
- `GET /api/v1/voice/options`
- `POST /api/v1/voice/generate`
- `GET /api/v1/system/tts`

Planned next API surface:

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

### What Is Now Outdated Or Too Narrow

- [web-app/WEB-AGENTS.md](./web-app/WEB-AGENTS.md) still frames the frontend as mainly:
  - browser-first image processing
  - extraction UI
  - crop/editor tooling

  It does not reflect that the frontend now also owns:
  - long-lived timeline state
  - backend voice orchestration
  - browser FFmpeg export
  - render progress, preview, and fallback logic

- The current frontend guide is missing a dedicated render/export specialization.
- The phrase `Browser-first architecture` is now too broad as a global frontend priority:
  - still true for upload/extract
  - no longer sufficient for export, because official export is moving to backend-native rendering

- [web-app/ai/design-rules.md](./web-app/ai/design-rules.md) is directionally useful, but the live app has drifted:
  - many screens use stronger glass and rounded card treatments than the rule document suggests
  - export/timeline screens are now more like a creator workstation than a lightweight editor pane

- Repo setup scripts still contain stale F5 setup messaging:
  - [setup.ps1](./setup.ps1)
  - [setup.sh](./setup.sh)

  These no longer match the active product direction.

### Recommended Rule Updates

1. Update `WEB-AGENTS.md` to split frontend scope into:
   - extraction/image workspace
   - application orchestration/state
   - render/export pipeline

2. Replace broad `Browser-first architecture` language with a more accurate split:
   - browser-first for ingest/extract/edit
   - backend-assisted for AI generation
   - backend-native as the target for official export

3. Add a frontend render/export rule set covering:
   - FFmpeg lifecycle
   - temp asset cleanup
   - progress reporting
   - failure surfacing
   - parity expectations between browser fallback and backend official export

4. Refresh design rules so they describe the actual product:
   - premium dark creator tool
   - denser control surfaces
   - modular workstation layout
   - restrained but intentional glow/glass usage

5. Remove stale F5 wording from setup scripts and setup guidance.

## Current Product Conclusions

1. One TTS path only should remain active: `vieneu + voice_default`.
2. `voice_default` must continue to be treated as a cached preset, not a per-request clone.
3. Browser render is now a working export tool, but not the right long-term official export engine.
4. Native backend render is the correct next architecture for speed, stability, and cancellation.
5. The repo rules are still usable, but frontend workflow guidance now needs a render/export-aware refresh.

## Next Actions

1. Implement the approved backend native render job architecture from [PLAN.md](./PLAN.md).
2. Implement the approved browser cinematic motion set from [PLAN_EXPORT.md](./PLAN_EXPORT.md).
3. Refresh `WEB-AGENTS.md`, frontend render workflow guidance, and design rules so they match the actual product.
4. Remove stale F5 setup references from setup scripts and setup docs.
5. Keep README, ROADMAP, and active env defaults synchronized whenever TTS or export decisions change.

## Open Risks

- Browser-side FFmpeg remains memory-heavy for long timelines until native backend export is in place.
- Motion upgrades on browser export will increase render cost before the backend-native path lands.
- Rebuilding `voice_default` from a different reference source will change the production narration voice globally.
- VieNeu standard mode still depends on a complete Python runtime with `torch`, `torchaudio`, `transformers`, `neucodec`, and `vieneu`.
