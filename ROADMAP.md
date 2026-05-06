# Manga Recap Tool - Roadmap

Last synchronized with the repo on `2026-05-07`.

## Current Product State

The active product is a frontend-backend manga/webtoon recap creator.

```text
manga-recap-tool/
|- web-app/     React + Vite creator UI
|- backend/     FastAPI backend
|- remotion/    Remotion composition/player code
|- PLAN.md      backend render architecture plan
`- ROADMAP.md   current implementation state
```

Active user flow:

```text
Upload -> Extract -> Script -> Voice -> Render
```

Current architecture:

- Upload and extraction stay browser-side.
- Step Script sends panel image files to backend Gemini.
- Step Voice runs through backend TTS routes.
- Multi-scene voice generation uses `POST /api/v1/voice/generate-batch`.
- Timeline state lives in the frontend store.
- Official MP4 export runs through backend async native `ffmpeg` render jobs.
- Remotion powers the preview/composition path and backend video production route.
- Browser-side media work remains useful for preview/fallback, but backend render is the official export path.

## Current Milestones

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | Done | FE-BE structure is stable. |
| M1 Upload/Extract | Done | Browser-side upload and extraction are active. |
| M2 Script | Done | Backend Gemini route is the production script path. |
| M3 Voice | Done | Backend voice generation is active, including batch generation for the Voice step. |
| M4 Timeline | Done | Frontend store owns narration edits, clip ordering, duplicate/remove/reset/move actions, audio status, and render intent. |
| M5 Backend Export | Done | Async render jobs with native `ffmpeg` are active. |
| M6 Remotion Preview/Video | Done | Remotion player and server-side production route are wired. |
| M7 Cinematic Effects | Done | Effect suggestion, VFX metadata, transitions, and Remotion composition support are active. |
| M8 Dynamic Quality | Done | Remotion render commands use aspect-aware CRF and `yuv420p`. |
| M9 Character Review | Dormant/WIP | Frontend character review code exists, but backend character routes are not registered in the current FastAPI app and the step is not in active navigation. |

## Completed Checkpoints

### Roadmap Sync And Follow-through (2026-05-07)

- Added `POST /api/v1/voice/generate-batch`.
- Added backend batch voice request/response models with per-item WAV payloads and TTS chunk diagnostics.
- Updated the frontend Voice step so bulk generation uses one backend request.
- Kept single-clip voice generation on `POST /api/v1/voice/generate`.
- Added backend tests for voice batch generation.
- Added Remotion quality flags:
  - vertical output: `--crf=23 --pixel-format=yuv420p`
  - horizontal output: `--crf=21 --pixel-format=yuv420p`
- Added tests for Remotion quality flag selection.
- Surfaced character diagnostics in the existing Character Review UI code.
- Restored timeline editor actions in the frontend store:
  - duplicate clip
  - reset clip narration to auto baseline
  - remove clip
  - move clip
- Fixed Windows test collection by replacing stdout/stderr wrapper replacement with `reconfigure()`.
- Restored TTS runtime status behavior through `ProviderRegistry`.
- Synced voice sample serving for `/assets/voice-samples/vieneu/voice-default.wav`.
- Cleaned TypeScript build blockers from unused imports and Remotion Player typing.
- Verified backend route coverage and frontend build.

### Cinematic Pipeline (2026-05-04)

- Added metadata-driven Remotion rendering.
- Added transition presets:
  - `crossfade`
  - `smooth_zoom_fade`
  - `dip_to_black`
  - `hard_cut`
- Added CSS/SVG VFX layers such as grain, rain, embers, camera shake, and edge glow.
- Decoupled scene audio from visual transition wrappers to avoid audio cut-offs during fades.
- Added backend effect suggestion route: `POST /api/v1/video/suggest-effects`.
- Added Remotion path aliases for cleaner imports.

### Render And Export

- Backend render jobs are active:
  - create job
  - poll status
  - stream result
  - reveal result on Windows
  - cancel job
  - TTL cleanup
- Frontend render submits a self-contained payload to the backend.
- Render progress surfaces phases and details instead of one generic failure.
- Browser preview/fallback remains deterministic at the render-plan level.

### Script Generation

- Backend Gemini is the production script path.
- Script generation accepts multipart panel uploads and structured context.
- Backend logs request, result, and error details for frontend inspection.
- Async script jobs exist alongside the direct generate route.

### Voice/TTS

- Active generation provider is `vietvoice`.
- Canonical voice key is `voice_default`.
- Frontend and backend env defaults now use `vietvoice`.
- Runtime status accepts `vieneu` as a compatibility alias, but generation should use `vietvoice`.
- Voice sample assets are served with cross-origin headers for frontend preview.
- Voice step uses batch generation for multiple clips and preserves the single route for one-off generation.

## Active API Surface

### Health

- `GET /api/v1/health`

### Script

- `POST /api/v1/script/generate`
- `POST /api/v1/script/jobs`
- `GET /api/v1/script/jobs/{job_id}`
- `GET /api/v1/script/jobs/{job_id}/result`
- `POST /api/v1/script/jobs/{job_id}/cancel`

### Voice

- `GET /api/v1/voice/options`
- `POST /api/v1/voice/generate`
- `POST /api/v1/voice/generate-batch`

### System

- `GET /api/v1/system/tts`

### Video / Remotion Production

- `POST /api/v1/video/suggest-effects`
- `POST /api/v1/video/tts-batch`
- `POST /api/v1/video/produce`
- `POST /api/v1/video/produce-from-narration`
- `GET /api/v1/video/jobs/{job_id}`
- `GET /api/v1/video/jobs/{job_id}/result`
- `POST /api/v1/video/jobs/{job_id}/cancel`
- `POST /api/v1/video/jobs/purge`

### Render Jobs

- `POST /api/v1/render/jobs`
- `GET /api/v1/render/jobs/{job_id}`
- `GET /api/v1/render/jobs/{job_id}/result`
- `POST /api/v1/render/jobs/{job_id}/reveal`
- `POST /api/v1/render/jobs/{job_id}/cancel`

### Dormant / Not Registered

The current FastAPI app does not include a character router. The frontend has character review code under `web-app/src/features/characters`, but these routes are not active:

- `/api/v1/characters/prepass`
- `/api/v1/characters/clusters`
- `/api/v1/characters/rename`
- `/api/v1/characters/merge`
- `/api/v1/characters/split`
- `/api/v1/characters/panel-mapping`
- `/api/v1/characters/crop-mapping`
- `/api/v1/characters/status`

## Runtime Requirements

### Frontend

- Node.js with npm workspaces.
- Vite dev server for `web-app`.

### Backend

- Python environment with `backend/requirements.txt`.
- `AI_BACKEND_GEMINI_API_KEY` for script generation and effect suggestion.
- Native `ffmpeg` in `PATH` or configured through `AI_BACKEND_RENDER_FFMPEG_PATH`.
- Local VietVoice runtime dependencies for TTS.

## Validation Snapshot

Passing on `2026-05-07`:

```bash
python -m pytest backend/tests/test_routes.py backend/tests/test_render_routes.py backend/tests/test_render_queue.py backend/tests/test_voice_routes.py backend/tests/test_video_orchestrator.py -q
npm --prefix web-app run build
npm --prefix web-app test -- --run src/shared/storage/useRecapStore.test.ts
```

Observed but non-blocking:

- `pytest-asyncio` warns about the future default fixture loop scope.
- Vite warns that the main frontend chunk is larger than 500 kB.

## Current Product Conclusions

1. The active product flow is `Upload -> Extract -> Script -> Voice -> Render`.
2. Backend Gemini owns production script generation.
3. Backend TTS owns voice generation; batch voice generation is the preferred path for multi-clip UI generation.
4. Timeline editing is centralized in the frontend store.
5. Backend native render is the official MP4 export path.
6. Remotion is the cinematic preview/composition system and the video production renderer.
7. TTS generation provider should be documented as `vietvoice`; `vieneu` remains a runtime/status compatibility label.
8. Character review should not be documented as active until backend routes are restored and the step is wired into app navigation.

## Next Actions

1. Decide whether to restore the backend character router or remove dormant character UI code.
2. If character review is restored, wire it into app navigation and add backend route tests before marking it active.
3. Continue tuning narration editing and render usability now that timeline actions are restored.
4. Add frontend code splitting for the large Vite output chunk.
5. Keep README, env examples, ROADMAP, and agent guides synchronized whenever TTS, render, or active flow changes.
6. Monitor longer real-world exports for ffmpeg availability, render job TTL cleanup, and host disk pressure.

## Open Risks

- Character review is currently not production-active because backend routes are missing.
- Browser media processing can remain memory-heavy for long chapters.
- Backend native export depends on a valid local `ffmpeg`.
- Gemini requests depend on backend API key configuration and rate limits.
- TTS runtime depends on local VietVoice dependencies and model/runtime availability.
- Remotion preview/player and backend render share data concepts, but browser preview and exported MP4 can still diverge if composition props drift.
