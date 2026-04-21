# manga-recap-tool

Frontend-backend manga recap editor.

## Repo layout

- `web-app/`: React + Vite editor for upload, extract, script, voice, and render flow
- `backend/`: FastAPI service for script generation and backend-owned TTS
- `ai/`: notes and internal references

## Current architecture

- Upload and extract stay browser-side
- Step Script sends extracted panel files from frontend to backend
- Backend runs Gemini script generation from panel images
- Voice generation runs through backend routes only
- Active TTS providers are:
  - `vieneu` as the default CPU-first path
  - `f5` as the ONNX worker path for benchmark / comparison

Active API entrypoints:

```text
POST /api/v1/script/generate
GET  /api/v1/voice/options
POST /api/v1/voice/generate
GET  /api/v1/system/tts
```

`GET /api/v1/system/tts` also accepts `?provider=vieneu` or `?provider=f5`.

## Setup

Frontend:

```bash
cd web-app
npm install
copy .env.example .env
```

Backend:

```bash
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
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
VITE_TTS_PROVIDER=vieneu
VITE_TTS_VOICE_KEY=default
```

## Backend env

`backend/.env`

```bash
AI_BACKEND_HOST=127.0.0.1
AI_BACKEND_PORT=8000
AI_BACKEND_GEMINI_API_KEY=
AI_BACKEND_GEMINI_MODEL=gemini-2.5-flash
AI_BACKEND_GEMINI_API_ENDPOINT=
AI_BACKEND_TTS_PROVIDER=vieneu
AI_BACKEND_TTS_RUNTIME=auto
AI_BACKEND_TTS_WARM_ON_STARTUP=false
AI_BACKEND_TTS_SMOKE_TEST_TEXT=
AI_BACKEND_TTS_MAX_CONCURRENT_JOBS=1
AI_BACKEND_TTS_VIENEU_VOICE_KEY=default
AI_BACKEND_TTS_F5_PYTHON=.bench/f5-venv/Scripts/python.exe
AI_BACKEND_TTS_F5_MODEL_ROOT=.models/f5-onnx
AI_BACKEND_TTS_F5_REFERENCE_ROOT=.models/f5-reference
AI_BACKEND_TTS_F5_VOICE_KEY=vietnamese_reference
AI_BACKEND_TTS_F5_GPU_BUNDLE=GPU_CUDA_F16
AI_BACKEND_TTS_F5_CPU_BUNDLE=CPU_F32
```

## Local model placement

See [backend/.models/README.md](./backend/.models/README.md).

In short:

- `vieneu` does not need checked-in model assets here
- `f5` expects ONNX bundles under `backend/.models/f5-onnx/`
- `f5` also needs at least one reference pair:
  - `backend/.models/f5-reference/<preset>.wav`
  - `backend/.models/f5-reference/<preset>.txt`

## Benchmark

Run the backend first, then execute:

```bash
cd backend
python .bench/bench_vieneu.py
```

Default output:

- `backend/.bench/samples/vieneu/sample.wav`
- `backend/.bench/samples/f5/sample.wav`
- `backend/.bench/samples/benchmark.json`

## Validation status

Verified on `2026-04-21`:

- `npm --prefix web-app run build`
- `pytest backend/tests/test_voice_routes.py backend/tests/test_routes.py`
- `python -m compileall backend/app backend/tests`

## Open risks

- `f5` quality depends heavily on the reference clip quality and text pairing
- `f5` GPU acceleration on Windows depends on the external ONNX runtime exposing `DmlExecutionProvider`
- Gemini script generation is still synchronous
