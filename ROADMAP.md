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

## Checkpoint: Translation & Automated Benchmarking (2026-04-16)

- Completed full English -> Vietnamese translation for Gemini script generation prompts (`_build_understanding_prompt`, `_build_narration_prompt`, `_build_narration_context_summary`).
- Updated `app.models.domain.Metrics` to track and return `totalPromptTokens`, `totalCandidatesTokens`, and `totalTokens` usage straight from the API.
- Implemented `test_score.py` within `ai-backend` for localized batch testing of chapter directories (e.g. `D:\Manhwa Recap\Tâm Ma\test 2`). This script fully runs the backend `GeminiScriptService`, captures latency & token metrics, and then executes an **automated Gemini benchmark** (scoring narrative tension, continuity, and overall score out of 10), and writes to `result.json`.
- *Note:* Live verification executed on proxy `http://127.0.0.1:8045` with the script yielded an `HTTP 429: Resource Exhausted` error. You can run the final test directly from the backend by calling `python test_score.py` whenever the proxy quota resets!

## Checkpoint: Async Pipeline, UI Dashboards & Optimization (2026-04-17)

- **Async Job Architecture:** Migrated AI script generation pipeline to an asynchronous job-based architecture. Implemented real-time log streaming via job polling.
- **Vision Pipeline Optimization:** Unified the vision-to-narration flow to reduce latency and token usage. Optimized panel image resolution to `512px` to resolve proxy constraints. Refined prompts for strict character identification.
- **Frontend UI & Observability:** Finalized the high-fidelity backend progress dashboard. Added OCR extraction logs to UI, fixed container layouts, and implemented collapsible raw data output sections with copy functionality. Restructured the "Panel Understanding" layout.
- **GPU Setup & Benchmarking:** Fixed AMD GPU compute offload (ROCm/Vulkan, `llama.cpp` fallback), added thermal safety cooldowns. Ran multi-model local benchmarks (`qwen3-vl:4b`, `qwen2.5vl:7b`, `gemma3`) for the vision-OCR pipeline.
- **Stability:** Executed a comprehensive project cache and temporary file cleanup across both `web-app` and `ai-backend`.

## Checkpoint: Minimal Character-Aware Prompt System (2026-04-17)

### Product direction

- Replaced the heavier character-system direction with a speed-first minimal layer for direct image-to-script generation.
- Character handling now exists only to support naming continuity and uncertainty control inside the final narration prompt.
- `mangaName` and `mainCharacter` are no longer required inputs for Step Script.

### Backend implementation

- Refactored [ai-backend/app/services/gemini_script_service.py](./ai-backend/app/services/gemini_script_service.py) around a compact direct-generation prompt.
- Added tiny memory shape in [ai-backend/app/models/domain.py](./ai-backend/app/models/domain.py):
  - `StoryMemory.summary`
  - `StoryMemory.recentNames`
- Added lightweight character hint selection:
  - inject at most 2 names
  - prefer names from `recentNames` and manual `mainCharacter`
  - fall back to neutral labels when identity is uncertain
- Added compact story-memory generation:
  - one short continuity summary per batch
  - keep at most 3 recent names
- Reduced default Gemini script batch size to `4` via `AI_BACKEND_GEMINI_SCRIPT_BATCH_SIZE` in [ai-backend/app/core/config.py](./ai-backend/app/core/config.py).

### Frontend implementation

- Updated [web-app/src/shared/types/index.ts](./web-app/src/shared/types/index.ts) so script context fields can stay optional.
- Updated [web-app/src/features/script/api/scriptApi.ts](./web-app/src/features/script/api/scriptApi.ts) to send only non-empty context fields.
- Updated [web-app/src/features/script/hooks/useScriptJob.ts](./web-app/src/features/script/hooks/useScriptJob.ts) so script generation no longer blocks on missing manga title or main-character hint.
- Updated [web-app/src/features/script/components/StepScript.tsx](./web-app/src/features/script/components/StepScript.tsx):
  - both context inputs are now marked optional
  - UI explains neutral fallback naming behavior
  - story memory UI shows recent injected names

### Validation

Completed on `2026-04-17`:
- `python -m pytest tests/test_gemini_script_service.py`
- `python -m compileall app tests/test_gemini_script_service.py`
- `npm --prefix web-app run build`

Added regression coverage in [ai-backend/tests/test_gemini_script_service.py](./ai-backend/tests/test_gemini_script_service.py):
- optional `ScriptContext` defaults
- compact prompt composition
- tiny memory + recent-name extraction

### Outcome

- Prompt is shorter and less rigid than the prior forced-name design.
- Naming is now optional and guarded by uncertainty rules.
- Continuity survives across adjacent batches without re-feeding large prior context.
- FE and BE contract now supports script generation even when title or character hints are missing.

## Milestone Status

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | Done | FE-BE structure restored. |
| M1 Extract | Done | Browser-side upload/extract is working perfectly. |
| M2 Script | Done | Backend Gemini baseline updated with async polling, token metrics, and the minimal character-aware prompt system. |
| M3 Voice | In Progress | Voice generation UI in FE, utilizing ElevenLabs. |
| M4 Timeline | In Progress | Separating MC narration from raw OCR; base timeline editor in active development. |
| M5 Render | Not started | Browser render/export pending. |

## Open Risks

- Local GPU setup (AMD stack) may require constant observation for compatibility when updating `llama.cpp` or Ollama.
- Large volume chapters using the concurrent async queue might still trigger `429 Quota Exhausted` on free Gemini proxy; need to ensure job retry/backoff handles this gracefully.
- Character hint selection currently uses lightweight continuity heuristics only; OCR-backed identity confirmation has not been folded into the active Gemini Step Script path yet.

## Next Actions

1. Extend character hint selection with stronger identity signals such as OCR dialogue or panel metadata without regressing prompt size.
2. Tune `AI_BACKEND_GEMINI_SCRIPT_BATCH_SIZE` with real chapter runs and lock the fastest stable production default.
3. Complete the M4 Timeline feature: fully integrate narrator/persona editing and finalize timeline UX for YouTube-style recap creation.
4. Advance M3 Voice integration logic against the new compact script output.
5. Keep monitoring proxy quota exhaustion behaviour and refine API request throttling if needed.
