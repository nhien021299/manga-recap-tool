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
- `ai-backend`: `PYTHONPATH=. .venv\Scripts\pytest.exe -q` passes
- `ai-backend`: `GET /api/v1/system/providers` now reports `visionModel=qwen2.5vl:7b`

## Checkpoint: M2 Debug Pass (2026-04-15)

### Scope covered
- Full-stack M2 debugging from cropped panel upload to final script result
- Real local validation with the user's cropped chapter folder
- Runtime stability, logging, prompt behavior, and output-quality review

### What was planned
- Restore frontend dev flow and confirm backend startup path
- Make backend caption/script failures observable instead of opaque
- Stabilize Ollama vision runs under long chapter workloads
- Compare raw `understanding` output against final `script` output
- Identify whether the main failure sits in runtime, prompt design, or model quality

### What was implemented

#### Frontend
- Fixed missing `vite` dependency path by reinstalling workspace dependencies
- Stabilized backend log rendering:
  - keep backend `timestamp` and `id`
  - avoid replacing log state when payload is unchanged
  - remove per-line flicker on polling refresh
  - show animated `...` loading state on the latest request log
- Exposed backend error `details` directly in the Script step UI

#### Backend
- Added clearer caption failure categories:
  - `caption raw provider error`
  - `caption JSON validation failed`
  - `caption repair failed`
  - `caption item count mismatch`
- Stopped collapsing all failures into a generic `Backend script pipeline failed`
- Added richer Ollama error context in logs:
  - provider
  - model
  - endpoint
  - timeout
  - retry count
  - batch index
  - panel ids
  - exception type
- Added vision timeout retry behavior after `ReadTimeout`
- Added caption image preprocessing before Ollama:
  - resize with aspect ratio preserved
  - convert to JPEG
  - configurable max width / height
- Tightened script generation validation:
  - exact item count per chunk
  - exact `panel_index` match
  - required `ai_view` and `voiceover_text`
  - retry invalid chunks instead of silently degrading to `Narration unavailable.`
- Reworked caption prompt to be visual-only:
  - removed story-lore anchoring from caption stage
  - kept language guidance
  - reserved story context for script stage instead

### Config / defaults adjusted
- Added `Pillow` to backend requirements for image preprocessing
- Caption flow tuned for safer local Ollama runs:
  - `AI_BACKEND_CAPTION_CHUNK_SIZE=1`
  - `AI_BACKEND_CAPTION_MAX_TOKENS=512`
- Vision runtime tuning added:
  - `AI_BACKEND_VISION_TIMEOUT_SECONDS`
  - `AI_BACKEND_VISION_TIMEOUT_RETRIES`
  - `AI_BACKEND_VISION_RETRY_DELAY_SECONDS`
  - `AI_BACKEND_VISION_MAX_WIDTH`
  - `AI_BACKEND_VISION_MAX_HEIGHT`
- Script validation / retry tuning added:
  - `AI_BACKEND_SCRIPT_GENERATION_RETRIES`
  - `AI_BACKEND_SCRIPT_RETRY_DELAY_SECONDS`

### Real local test runs completed
Input used:
- Cropped chapter folder: `D:\Manhwa Recap\Tâm Ma\chapter 1 cropped`
- Total panels tested: `52`

Run 1:
- Status: completed
- Metrics:
  - `totalMs=221210`
  - `captionMs=157661`
  - `scriptMs=63547`
- Result:
  - runtime passed
  - caption output was heavily contaminated by lore / main-character leakage
  - script output inherited those errors

Run 2 after visual-only caption patch:
- Status: completed
- Metrics:
  - `totalMs=212876`
  - `captionMs=153325`
  - `scriptMs=59549`
- Result:
  - runtime passed again
  - lore contamination dropped sharply
  - output became too generic at caption stage
  - script structure improved, but quality still remained weak because the caption input stayed weak

Run 3 after switching vision model to `qwen2.5vl:7b`:
- Status: completed
- Metrics:
  - `totalMs=313521`
  - `captionMs=246823`
  - `scriptMs=66697`
- Result:
  - runtime passed on the same 52-panel chapter with `0` backend error logs
  - caption specificity improved sharply versus `gemma3`
  - `27/52` panels now contain non-empty dialogue extraction
  - `40/52` panels now contain non-empty SFX extraction
  - `52/52` panel summaries are unique instead of collapsing into repeated generic lines
  - quality is still inconsistent because roughly half of the caption output drifts into English instead of staying in Vietnamese
  - progress reporting is still too coarse because the job sat at `10%` until completion

### What has been confirmed
- The current M2 backend no longer has a primary runtime blocker for this chapter
- The earlier `ReadTimeout` issue can be mitigated by shorter timeout + delay + retry
- Resize with preserved aspect ratio is not the main quality problem
- Switching the vision model from `gemma3` to `qwen2.5vl:7b` materially improves caption specificity and dialogue pickup on this dataset
- The current quality bottleneck is now the caption-stage normalization / language consistency, not basic caption uniqueness
- The script stage is no longer the main failure source once schema validation and retries are enforced

### Current unresolved issues
- `qwen2.5vl:7b` is slower than the previous `gemma3` baseline on this machine by about `100.6s` total (`313521ms` vs `212876ms`)
- Caption output still mixes Vietnamese and English on the same run; roughly `26/52` understandings contain obvious English phrasing
- Some extracted SFX tokens are noisy or semantically wrong for Vietnamese output quality
- Final narration is stronger than before, but it still inherits caption-stage inconsistencies
- Fine-grained progress is still coarse
- Long-run quality benchmarking across different local models has not been completed yet

### Recommended next solutions
1. Keep the current caption visual-only prompt design; do not reintroduce lore into caption stage.
2. Keep `qwen2.5vl:7b` as the active local vision default for now because it is the first tested model that clearly improves caption specificity on the real chapter.
3. Add caption-output normalization so the vision stage always returns Vietnamese-only fields before handing off to script generation.
4. Add a dedicated OCR-aware path or post-pass for dialogue / SFX cleanup, because raw vision extraction is now detailed enough to justify cleanup work.
5. Continue benchmarking at least one more stronger-or-faster alternative:
   - `llama3.2-vision`
   - `gemma3:12b` if hardware allows
6. Improve backend progress reporting so long caption batches do not appear stuck at `10%`.

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
- text model: `gemma3`
- vision model: `qwen2.5vl:7b`

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
