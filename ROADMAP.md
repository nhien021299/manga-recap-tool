# Manga Recap Tool - Executive Roadmap

## Current State

Repo is now split into:

```text
manga-recap-tool/
├── web-app/
├── ai-backend/
├── ai/
└── ROADMAP.md
```

- `web-app/`: browser-first editor for upload, extract, panel editing, script review, and current voice flow
- `ai-backend/`: FastAPI local AI backend for caption + script jobs with provider adapters

Verified today:
- `web-app`: `npm run build` passes
- `ai-backend`: `python -m pytest` passes

## Milestone Status

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | In progress | Monorepo split is done; UI/component cleanup still remains |
| M1 Extract | Largely done | Upload, detect, edit, export, panel reuse, IndexedDB persistence are working |
| M2 Script | In progress | Script flow moved from browser direct model calls to backend job queue + polling |
| M3 Voice | Partial | ElevenLabs flow works in frontend; local/backend TTS is deferred |
| M4 Timeline | Not started | Only base timeline state/readiness exists |
| M5 Render | Not started | Browser render/export still pending |

## What Is Done

### Web App
- Reorganized app toward `app/`, `shared/`, `features/`
- Centralized store and shared types
- Replaced frontend direct AI calls with backend API client + polling job hook
- Added persisted script job state
- Kept Upload and Extract fully browser-first
- Kept voice config separate from backend config
- Removed old frontend local-model pipeline files

### AI Backend
- Added FastAPI app with:
  - `health`
  - `system/providers`
  - `caption/batch`
  - `script/jobs`
  - `script job status/result/cancel`
- Added provider abstraction:
  - `ollama_text`
  - `ollama_vision`
  - `llama_cpp_text`
- Added in-process async job queue
- Added caption pipeline, script pipeline, temp-file handling, and basic tests

## What Is Not Done Yet

- Real local-model validation on your machine with actual chapter workloads
- Fine-grained backend progress reporting
- Full resume/reconnect behavior for long-running jobs after hard refresh
- IndexedDB persistence for generated audio blobs
- Dedicated timeline editing and duration logic
- Video render/export pipeline

## Known Risks

### Local Vision Throughput
- The backend contract is ready, but real throughput depends on the actual vision model you run through Ollama.
- If the selected vision model is too large, `60-80` panels may exceed the `< 2 min` target even with warmed models.

### AMD Windows Runtime Variability
- Your app architecture is now prepared for local inference, but Windows + AMD can still vary a lot in real inference speed depending on:
  - Ollama build behavior
  - model quantization
  - GPU offload effectiveness
  - concurrent RAM pressure from browser + backend + model runtime

### Polling vs true progress
- Current frontend status is polling-based and reliable enough for v1, but progress is still coarse.
- Users may see long stretches with little visible movement during heavy caption or script batches.

### Large chapter memory pressure
- Upload/extract remains browser-first and memory-safe by design, but real large chapters can still stress:
  - browser image decode memory
  - IndexedDB blob persistence
  - backend temp file disk usage

## Next Actions

### 1. Validate backend on your machine
Run:

```bash
cd ai-backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run frontend:

```bash
cd web-app
npm run dev
```

Confirm:
- `Settings -> AI Backend URL = http://localhost:8000`
- `GET /api/v1/health` returns `ok`
- `GET /api/v1/system/providers` returns expected provider/model config

### 2. Validate Ollama provider path
Set `ai-backend/.env` from `.env.example` and start with:
- text model: your existing `llama3`
- vision model: a small Ollama vision model profile first

Then confirm:
- single 10-panel job completes
- result returns `understandings`, `generatedItems`, `storyMemories`
- no malformed JSON loop occurs

### 3. Benchmark real latency on your hardware
Test these workloads in order:
- 10 panels
- 30 panels
- 60 panels
- 80 panels

For each run, record:
- total time
- caption stage feel / bottleneck
- script stage feel / bottleneck
- RAM usage
- VRAM usage
- whether Ollama actually uses GPU effectively

Target:
- warmed `60-80` panel run under `2 min`

### 4. Tune if latency misses target
If too slow, adjust in this order:
- reduce vision model size first
- reduce prompt verbosity second
- keep caption chunk at `4` initially, then test `6`
- keep script chunk at `10`, then test `12`
- only consider `llama.cpp` text path if Ollama text becomes the bottleneck

### 5. Harden M2 after first real runs
- Add metrics/log persistence per job
- Improve backend progress percentages by stage
- Add malformed-output regression tests from real failed outputs
- Add optional cached reuse of structured understandings across repeated runs

### 6. Then continue roadmap
- finish M3 persistence
- start M4 timeline logic
- start M5 render MVP

## Recommended Immediate Priority

Do not add new product features next.

Do this next:
1. Run the backend and frontend together locally
2. Validate one real chapter end-to-end
3. Measure 10/30/60/80 panel latency
4. Tune model/profile for your machine
5. Only then continue deeper into timeline/render
