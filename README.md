# manga-recap-tool

Frontend-backend manga recap editor.

## Repo layout

- `web-app/`: React + Vite editor for upload, extract, script, voice, and render flow
- `ai-backend/`: FastAPI service for Step Script generation
- `ai/`: notes and internal references

## Current architecture

- Upload and extract stay browser-side
- Step Script sends extracted panel files from frontend to backend
- Backend runs Gemini script generation from panel images with chunk continuity
- Frontend hydrates `storyMemories`, `timeline`, raw outputs, and logs
- Voice generation stays frontend-side with ElevenLabs

Active Step Script entrypoint:

```text
POST /api/v1/script/generate
```

## Setup

Frontend:

```bash
cd web-app
npm install
copy .env.example .env
```

Backend:

```bash
cd ai-backend
python -m pip install -r requirements.txt
copy .env.example .env
```

Preferred backend credential:

```bash
AI_BACKEND_GEMINI_API_KEY=
```

## Run

From repo root:

```bash
npm run dev:be
npm run dev:web
```

Or use:

```bash
./start-dev.ps1
```

## Frontend env

`web-app/.env`

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_GEMINI_API_KEY=
VITE_ELEVENLABS_API_KEY=
VITE_TTS_VOICE_ID=pNInz6obpgmqS29pXo3W
VITE_TTS_MODEL=eleven_multilingual_v2
```

## Backend env

`ai-backend/.env`

```bash
AI_BACKEND_HOST=127.0.0.1
AI_BACKEND_PORT=8000
AI_BACKEND_GEMINI_API_KEY=
AI_BACKEND_GEMINI_MODEL=gemini-2.5-flash
AI_BACKEND_GEMINI_API_ENDPOINT=
AI_BACKEND_GEMINI_SCRIPT_BATCH_SIZE=4
AI_BACKEND_GEMINI_IDENTITY_EXPERIMENT_ENABLED=true
AI_BACKEND_GEMINI_IDENTITY_OCR_MIN_CONFIDENCE=0.70
AI_BACKEND_GEMINI_IDENTITY_OCR_MAX_TEXT_LINES=8
AI_BACKEND_GEMINI_MAX_CONCURRENT_REQUESTS=1
AI_BACKEND_GEMINI_MIN_REQUEST_INTERVAL_MS=750
AI_BACKEND_GEMINI_RETRY_ATTEMPTS=4
AI_BACKEND_GEMINI_RETRY_BASE_DELAY_MS=2000
AI_BACKEND_GEMINI_RETRY_MAX_DELAY_MS=15000
AI_BACKEND_GEMINI_COOLDOWN_ON_429_MS=20000
```

## M2 Script

M2 is the active backend Gemini Step Script flow.

- Active route stays `POST /api/v1/script/generate`
- FE-BE request and response contract stays stable
- Backend generates narration directly from uploaded panel images in batches
- Chunk continuity stays in `storyMemories`
- OCR for identity is enabled by default and uses PaddleOCR

### M2 improvements

- Identity signals:
  - Candidate names come only from `mainCharacter` and `previous_memory.recentNames`
  - Identity OCR uses PaddleOCR to confirm existing candidate names
  - OCR does not discover new names and does not do speaker attribution
  - Prompt now separates:
    - confirmed names from visible text/dialogue in the current batch
    - carryover names from previous chunk
  - If no name is confirmed, the prompt forces neutral labels

- Batch latency:
  - Runtime still uses `AI_BACKEND_GEMINI_SCRIPT_BATCH_SIZE`
  - Default production batch size remains `4`
  - Benchmarking is now done offline through `ai-backend/test_score.py`
  - The benchmark runs a matrix of batch sizes such as `2,4,6,8` and reports a recommended batch size without changing production defaults

- Quota stability:
  - Backend now uses a shared Gemini request gate across sync route and queue path
  - Gate enforces:
    - process-level concurrency limit
    - minimum spacing between requests
    - global cooldown after transient rate-limit/provider failures
  - Retry policy now covers `429`, `500`, `502`, `503`, `504`, timeout, and connection failures
  - `Retry-After` is used when provided; otherwise exponential backoff with jitter is used

### M2 metrics and logs

`metrics` now includes:

- `batchSizeUsed`
- `retryCount`
- `rateLimitedCount`
- `throttleWaitMs`
- `identityOcrMs`
- `identityConfirmedCount`
- `totalPromptTokens`
- `totalCandidatesTokens`
- `totalTokens`

Logs remain in the same `type/message/details` shape, with extra details for:

- identity evidence
- retry attempts
- cooldown scheduling
- benchmark output

### M2 benchmark

Run from `ai-backend`:

```bash
python test_score.py --chapter-dir <chapter1> --chapter-dir <chapter2> --chapter-dir <chapter3>
```

Optional flags:

```bash
python test_score.py --chapter-dir <chapter> --batch-sizes 2,4,6,8 --output benchmark_out/m2_gemini_latency
```

The script writes:

- `result.json`: raw run-level results per chapter and batch size
- `summary.json`: aggregate summary including `recommendedBatchSize`

## Validation status

Verified on `2026-04-20`:
- `npm run build:web` passes
- `python -m compileall app tests test_score.py`
- `pytest` in `ai-backend` passes

## Open risks

- Real chapter benchmarking on representative chapter sets is still pending
- Backend Gemini route is synchronous and cannot be cancelled mid-request
- Identity OCR is still a confirmation-only experiment and is disabled by default
- Legacy local-AI backend modules still exist in the repo but are not part of the active product flow
