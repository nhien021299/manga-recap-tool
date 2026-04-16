# Manga Recap Tool - Executive Roadmap

## Current State

Repo is active as a frontend-backend product:

```text
manga-recap-tool/
├── web-app/
├── ai-backend/
├── ai/
└── ROADMAP.md
```

- `web-app/`: upload, extract, script, voice, and render UI
- `ai-backend/`: FastAPI service for Step Script generation
- `ai/`: notes and internal references

Verified on `2026-04-16`:
- `npm run build:web` passes
- backend import passes after dependency install
- backend Gemini smoke test passes through `POST /api/v1/script/generate`

## Checkpoint: Backend Gemini Reintegration (2026-04-16)

### Product decision

- Keep FE-BE structure
- Do not use Ollama, llama.cpp, or OCR in the active Step Script product flow
- Move Gemini calls from browser down to backend
- Keep ElevenLabs voice generation frontend-side
- Prefer `AI_BACKEND_GEMINI_API_KEY` as the backend credential source
- Keep temporary fallback support for `web-app/.env -> VITE_GEMINI_API_KEY`

### Active architecture

Frontend:
- Upload and extract remain browser-side
- Step Script uploads panel files to backend
- Frontend stores `panelUnderstandings`, `storyMemories`, `timeline`, `rawOutput`, and logs
- Settings now use `apiBaseUrl` instead of browser-side Gemini key for Step Script

Backend:
- Active Step Script entrypoint is `POST /api/v1/script/generate`
- Backend runs a 2-stage Gemini pipeline:
  - stage 1: panel understanding
  - stage 2: narration generation with chunk continuity
- Backend returns:
  - `understandings`
  - `generatedItems`
  - `storyMemories`
  - `rawOutputs`
  - `metrics`
  - `logs`

### Current Step Script flow

1. Frontend collects extracted panels and script context.
2. Frontend sends multipart form-data to `/api/v1/script/generate`.
3. Backend saves temp uploads and calls Gemini stage 1 for panel understanding.
4. Backend calls Gemini stage 2 for narration using structured understandings and previous chunk memory.
5. Backend returns normalized result payload plus logs and metrics.
6. Frontend hydrates `panelUnderstandings`, `storyMemories`, `timeline`, and raw output snapshots.

## What Was Implemented

### Frontend

- Replaced `gemini-direct` Script flow with backend API orchestration
- Added [web-app/src/features/script/api/scriptApi.ts](./web-app/src/features/script/api/scriptApi.ts)
- Rewrote [web-app/src/features/script/hooks/useScriptJob.ts](./web-app/src/features/script/hooks/useScriptJob.ts) to call backend Gemini
- Updated [web-app/src/features/script/components/StepScript.tsx](./web-app/src/features/script/components/StepScript.tsx) to reflect backend pipeline
- Updated [web-app/src/features/script/components/ScriptLogs.tsx](./web-app/src/features/script/components/ScriptLogs.tsx)
- Removed browser-direct Gemini client from active product path
- Restored `apiBaseUrl` in persisted app config

### Backend

- Added Gemini backend service in [ai-backend/app/services/gemini_script_service.py](./ai-backend/app/services/gemini_script_service.py)
- Added synchronous route `POST /api/v1/script/generate`
- Added backend Gemini config:
  - `AI_BACKEND_GEMINI_API_KEY`
  - `AI_BACKEND_GEMINI_MODEL`
- Added fallback loading from `web-app/.env -> VITE_GEMINI_API_KEY`
- Added retry/backoff for retryable Gemini failures:
  - `429`
  - `500`
  - `503`
- Hardened backend logging so `httpx/httpcore` no longer emit request URLs containing query-string API keys at `INFO`

### Dev and docs

- Restored FE-BE startup scripts:
  - [start-dev.ps1](./start-dev.ps1)
  - [start-dev.bat](./start-dev.bat)
- Added root script `npm run dev:be`
- Updated:
  - [README.md](./README.md)
  - [AGENTS.md](./AGENTS.md)
  - [web-app/README.md](./web-app/README.md)
  - [web-app/.env.example](./web-app/.env.example)
  - [ai-backend/.env.example](./ai-backend/.env.example)

## Runtime Status

Current local setup on `2026-04-16`:
- `ai-backend/.env` exists locally
- backend Gemini key is configured locally
- backend dependencies were installed from `ai-backend/requirements.txt`

Current dev start path:

```bash
npm run dev:be
npm run dev:web
```

Or use:

```bash
./start-dev.ps1
```

## Validation Status

Completed:
- `npm run build:web`
- `python -m py_compile` on touched backend modules
- backend import and settings check
- backend smoke test with synthetic panel through `POST /api/v1/script/generate`

Smoke test result summary:
- status: `200 OK`
- Gemini stage 1 succeeded
- Gemini stage 2 succeeded
- response shape matched expected frontend contract

Fixed during validation:
- missing Python imaging dependency in runtime environment until backend deps were installed
- raw `httpx` request logging exposed full Gemini URL including query-string key
- backend initially had no retry path for transient Gemini `503`

## Milestone Status

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | Done for current direction | FE-BE structure restored and active Step Script flow is backend Gemini |
| M1 Extract | Largely done | Browser-side upload/extract remains active |
| M2 Script | Done for backend Gemini baseline | FE calls BE, BE calls Gemini, store hydration is working |
| M3 Voice | Partial | ElevenLabs flow stays frontend-side |
| M4 Timeline | Not started | Only base timeline editing exists |
| M5 Render | Not started | Browser render/export still pending |

## Open Risks

- Chapter-scale validation is still pending on real workloads such as `10` and `52` panels
- Backend repo still contains legacy local-AI code paths that are not part of the active product flow
- `POST /api/v1/script/generate` is currently synchronous and cannot be cancelled mid-request
- Gemini prompt quality has only been smoke-tested, not yet tuned on production-like chapters

## Next Actions

1. Run end-to-end validation on a real extracted chapter workload from the UI.
2. Prefer moving the Gemini key permanently into `ai-backend/.env` and stop depending on `web-app/.env` fallback.
3. Decide whether to keep or archive the legacy local-AI backend modules.
4. If long chapter latency becomes a UX problem, add async job orchestration for the backend Gemini route without reintroducing local model runtime.
