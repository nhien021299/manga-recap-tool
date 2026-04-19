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

Verified on `2026-04-20`:
- `npm run build:web` passes
- `pytest` in `ai-backend` passes
- `python -m compileall app tests test_score.py` passes
- backend Gemini Step Script path remains active at `POST /api/v1/script/generate`

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

## Checkpoint: M2 Prompt Upgrade, Benchmark UI & PaddleOCR Activation (2026-04-20)

### Product direction

- Keep M2 as the active Gemini backend script path.
- Improve narration quality primarily through prompt design, not API or schema changes.
- Add user-visible benchmark capture and comparison in the frontend.
- Turn identity OCR on by default and standardize on PaddleOCR.

### Backend implementation

- Upgraded [ai-backend/app/services/gemini_script_service.py](./ai-backend/app/services/gemini_script_service.py) to a stronger `update 2.1` prompt:
  - added batch-level narration mode inference (`horror`, `combat`, `escape`, `investigation`, `aftermath`, `mystery`)
  - added retention-oriented style rules, lexical anti-generic rules, and batch-flow ending rules
  - kept current FE-BE contract, parsing discipline, retry logic, metrics, and identity evidence structure unchanged
  - kept `1 to 2 short sentences per panel` for TTS and JSON stability
- Refined unnamed-character handling in the prompt:
  - prefer descriptors based on visible age, outfit, role, weapon, job, or standout traits
  - avoid flat labels like `nam nhan` when the image supports a better description
  - keep the same descriptor across adjacent panels when the same unnamed person appears again
  - avoid switching guessed jobs/roles across nearby panels without strong visual proof
  - allow only a very light layer of Vietnamese Gen Z phrasing without breaking the cinematic recap tone
- Enabled identity OCR by default in [ai-backend/app/core/config.py](./ai-backend/app/core/config.py):
  - `AI_BACKEND_GEMINI_IDENTITY_EXPERIMENT_ENABLED=true`
- Switched OCR defaults to PaddleOCR in:
  - [ai-backend/.env.example](./ai-backend/.env.example)
  - local [ai-backend/.env](./ai-backend/.env)
  - [README.md](./README.md)
- Added `paddlepaddle` to [ai-backend/requirements.txt](./ai-backend/requirements.txt) and improved PaddleOCR error reporting in [ai-backend/app/providers/ocr/paddleocr_provider.py](./ai-backend/app/providers/ocr/paddleocr_provider.py) so missing framework installs now produce an explicit fix path instead of a vague import failure.

### Frontend implementation

- Added a dedicated `Benchmark` step in the sidebar and app routing.
- Added benchmark record storage in the frontend store.
- Added a `Save benchmark` action in the Script step:
  - merges all `voiceover_text` into one continuous block
  - appends `Gemini script generation completed.` plus metrics JSON
  - stores a benchmark record for later comparison
- Added benchmark scoring and comparison UI:
  - score dimensions include coverage, script usefulness, story continuity, latency, and stability/efficiency
  - users can select 2 saved runs and compare scores and metrics side by side
- Added fallback logic so benchmark save still works for older generated script states by reading metrics back from the latest `Gemini script generation completed.` log entry.

### Validation

Completed on `2026-04-20`:
- `npm run build:web`
- `pytest ai-backend/tests/test_routes.py ai-backend/tests/test_gemini_script_service.py ai-backend/tests/test_caption_service.py`
- `pytest tests/test_gemini_script_service.py tests/test_caption_service.py` inside `ai-backend`
- `python -m compileall app tests test_score.py`
- verified `import paddle` and `from paddleocr import PaddleOCR` in the active backend Python environment

### Outcome

- M2 narration is now more directed, more continuous, and less generic while staying within the current project structure.
- Identity OCR is now active by default and routed through PaddleOCR.
- Benchmarking now exists both offline in backend scripts and directly in the frontend for run-to-run comparison.
- M2 remains synchronous and contract-stable, but with stronger observability and better script-quality controls.

## Milestone Status

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | Done | FE-BE structure restored. |
| M1 Extract | Done | Browser-side upload/extract is working perfectly. |
| M2 Script | Done | Backend Gemini path is active with prompt update 2.1, token/latency metrics, frontend benchmark UI, and PaddleOCR-backed identity OCR enabled by default. |
| M3 Voice | In Progress | Voice generation UI in FE, utilizing ElevenLabs. |
| M4 Timeline | In Progress | Separating MC narration from raw OCR; base timeline editor in active development. |
| M5 Render | Not started | Browser render/export pending. |

## Open Risks

- Local GPU setup (AMD stack) may require constant observation for compatibility when updating `llama.cpp` or Ollama.
- Large volume chapters using the concurrent async queue might still trigger `429 Quota Exhausted` on free Gemini proxy; need to ensure job retry/backoff handles this gracefully.
- Identity OCR now runs in the active Gemini Step Script path, but it is still confirmation-only and does not discover new names or solve full speaker attribution.
- Prompt quality is improved, but real chapter evaluation is still needed to verify that stronger descriptors and light Gen Z phrasing do not overfit specific story tones.
- PaddleOCR is now a hard runtime dependency for the default OCR path; local environment drift can still break startup if dependencies are not installed from `requirements.txt`.

## Next Actions

1. Run real-chapter M2 evaluation with PaddleOCR on representative series to validate descriptor continuity, naming stability, and script tone.
2. Tune `AI_BACKEND_GEMINI_SCRIPT_BATCH_SIZE` with real chapter runs and lock the fastest stable production default.
3. Decide whether identity OCR should remain confirmation-only or expand carefully into stronger continuity signals without inflating hallucination risk.
4. Complete the M4 Timeline feature: fully integrate narrator/persona editing and finalize timeline UX for YouTube-style recap creation.
5. Advance M3 Voice integration logic against the stronger update 2.1 script output and benchmark audio pacing against the new narration style.
