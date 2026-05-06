# manga-recap-tool

Frontend-backend manga/webtoon recap editor.

## Current Status

The runnable product is a browser-first editor with a FastAPI backend for AI script generation, local Vietnamese TTS, effect planning, and MP4 rendering.

Active user flow:

```text
Upload -> Extract -> Script -> Voice -> Render
```

Current repo shape:

```text
manga-recap-tool/
|- web-app/     React + Vite editor
|- backend/     FastAPI API service
|- remotion/    Remotion composition/player code
|- PLAN.md      backend render plan
|- ROADMAP.md   current implementation status
`- AGENTS.md    agent routing guide
```

## Architecture

- Upload and panel extraction are browser-side.
- Script generation sends extracted panel files to backend Gemini through `POST /api/v1/script/generate`.
- Voice generation runs through backend TTS routes. Bulk scene generation uses `POST /api/v1/voice/generate-batch`.
- Timeline state, narration edits, audio status, clip order, and render intent live in the frontend store.
- Final MP4 export uses backend async render jobs with native `ffmpeg`.
- Remotion powers the cinematic preview/player path and server-side video production route.
- Backend Remotion renders now apply aspect-aware H.264 compression:
  - vertical: `--crf=23 --pixel-format=yuv420p`
  - horizontal: `--crf=21 --pixel-format=yuv420p`

## Active API Surface

```text
GET  /api/v1/health

POST /api/v1/script/generate
POST /api/v1/script/jobs
GET  /api/v1/script/jobs/{job_id}
GET  /api/v1/script/jobs/{job_id}/result
POST /api/v1/script/jobs/{job_id}/cancel

GET  /api/v1/voice/options
POST /api/v1/voice/generate
POST /api/v1/voice/generate-batch

GET  /api/v1/system/tts

POST /api/v1/video/suggest-effects
POST /api/v1/video/tts-batch
POST /api/v1/video/produce
POST /api/v1/video/produce-from-narration
GET  /api/v1/video/jobs/{job_id}
GET  /api/v1/video/jobs/{job_id}/result
POST /api/v1/video/jobs/{job_id}/cancel
POST /api/v1/video/jobs/purge

POST /api/v1/render/jobs
GET  /api/v1/render/jobs/{job_id}
GET  /api/v1/render/jobs/{job_id}/result
POST /api/v1/render/jobs/{job_id}/reveal
POST /api/v1/render/jobs/{job_id}/cancel
```

There is frontend character review code in `web-app/src/features/characters`, but no registered backend character router in the current FastAPI app. Treat character review as dormant/WIP until backend routes are restored and wired into app navigation.

## Setup

Install root workspace dependencies:

```bash
npm install
```

Install backend dependencies:

```bash
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
```

Create frontend env:

```bash
cd web-app
copy .env.example .env
```

## Run

From the repo root, run the backend and frontend in separate terminals:

```bash
npm run dev:be
npm run dev:web
```

Or on Windows:

```powershell
./start-dev.ps1
```

Default URLs:

```text
Backend:  http://127.0.0.1:8000
Frontend: http://127.0.0.1:5173
```

## Environment

`web-app/.env`

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_GEMINI_API_KEY=
VITE_TTS_PROVIDER=vietvoice
VITE_TTS_VOICE_KEY=voice_default
```

`backend/.env`

```bash
AI_BACKEND_HOST=127.0.0.1
AI_BACKEND_PORT=8000
AI_BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
AI_BACKEND_TEMP_ROOT=.temp/jobs

AI_BACKEND_GEMINI_API_KEY=
AI_BACKEND_GEMINI_MODEL=gemini-2.5-flash
AI_BACKEND_GEMINI_SCRIPT_BATCH_SIZE=4
AI_BACKEND_GEMINI_MAX_CONCURRENT_REQUESTS=1
AI_BACKEND_GEMINI_MIN_REQUEST_INTERVAL_MS=750
AI_BACKEND_GEMINI_RETRY_ATTEMPTS=4
AI_BACKEND_GEMINI_RETRY_BASE_DELAY_MS=2000
AI_BACKEND_GEMINI_RETRY_MAX_DELAY_MS=15000
AI_BACKEND_GEMINI_COOLDOWN_ON_429_MS=20000

AI_BACKEND_RENDER_TEMP_ROOT=.temp/render-jobs
AI_BACKEND_RENDER_FFMPEG_PATH=ffmpeg
AI_BACKEND_RENDER_RESULT_TTL_SECONDS=3600

AI_BACKEND_TTS_PROVIDER=vietvoice
AI_BACKEND_TTS_RUNTIME=auto
AI_BACKEND_TTS_WARM_ON_STARTUP=false
AI_BACKEND_TTS_SMOKE_TEST_TEXT=
AI_BACKEND_TTS_MAX_CONCURRENT_JOBS=1

AI_BACKEND_TTS_VIETVOICE_RUNTIME=directml
AI_BACKEND_TTS_VIETVOICE_VOICE_KEY=voice_default
AI_BACKEND_TTS_VIETVOICE_REF_ROOT=app/services/tts/vietvoice/refs
AI_BACKEND_TTS_VIETVOICE_OUTPUT_ROOT=.temp/tts-vietvoice
```

## TTS

The active voice path is the local `vietvoice` provider:

- frontend default provider: `vietvoice`
- backend config default: `AI_BACKEND_TTS_PROVIDER=vietvoice`
- canonical voice key: `voice_default`
- implementation: `backend/app/services/tts/vietvoice`

The runtime status endpoint accepts `provider=vieneu` as a compatibility alias and reports VieNeu-compatible model metadata, but request generation should use `vietvoice`.

Voice samples are served from:

```text
/assets/voice-samples/voice_default.wav
/assets/voice-samples/vieneu/voice-default.wav
```

## Export Runtime

Official export requires a native `ffmpeg` binary available to the backend.

Defaults:

- `AI_BACKEND_RENDER_FFMPEG_PATH=ffmpeg`
- temp render jobs: `backend/.temp/render-jobs`
- completed MP4 retention: `AI_BACKEND_RENDER_RESULT_TTL_SECONDS=3600`

The frontend submits one render payload, polls progress, previews the completed result, can download the MP4, and can reveal the output file on Windows.

## Validation

Commands validated for the current repo state:

```bash
python -m pytest backend/tests/test_routes.py backend/tests/test_render_routes.py backend/tests/test_render_queue.py backend/tests/test_voice_routes.py backend/tests/test_video_orchestrator.py -q
npm --prefix web-app run build
npm --prefix web-app test -- --run src/shared/storage/useRecapStore.test.ts
```

Current known warning:

- Vite reports a large output chunk after build. The build succeeds; code splitting is a future optimization.
