# manga-recap-tool

Frontend-backend manga recap editor.

## Current architecture

- `web-app/`: React + Vite editor for upload, extract, script, voice, and render flow
- `backend/`: FastAPI service for Gemini script generation and backend-owned TTS
- `ai/`: notes and internal references

Active product flow:

- Upload and extract stay browser-side
- Step Script sends extracted panel files from frontend to backend
- Backend runs Gemini script generation from panel images
- Step TTS runs only through backend routes
- The only active TTS provider is `vieneu`
- The active TTS model is `pnnbao-ump/VieNeu-TTS-0.3B`
- The active cached preset is `voice_default`

Active API entrypoints:

```text
POST /api/v1/script/generate
GET  /api/v1/voice/options
POST /api/v1/voice/generate
GET  /api/v1/system/tts
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
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
```

## TTS setup

The backend is now standardized on `VieNeu-TTS-0.3B` in `standard` mode with a cached preset.

Required files for the canonical project voice:

```text
backend/.models/voice-cache/voice_default/reference.wav
backend/.models/voice-cache/voice_default/reference.txt
```

To rebuild the preset cache:

```bash
python backend/scripts/build_voice_default_preset.py --source-key voice_default --voice-key voice_default --device cpu
```

This writes:

```text
backend/.models/vieneu-voices/voices.json
backend/.models/vieneu-voices/clone-cache.json
backend/.models/vieneu-voices/voice_default.wav
backend/.models/vieneu-voices/voice_default.txt
```

Runtime behavior:

- The backend loads `voices.json` once
- `voice_default` is reused for every TTS request
- The backend does not encode `reference.wav` again on each request

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
VITE_TTS_VOICE_KEY=voice_default
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
AI_BACKEND_TTS_VIENEU_MODEL_ID=pnnbao-ump/VieNeu-TTS-0.3B
AI_BACKEND_TTS_VIENEU_TEMPERATURE=1.0
AI_BACKEND_TTS_VIENEU_VOICE_KEY=voice_default
AI_BACKEND_TTS_VIENEU_VOICE_ROOT=.models/vieneu-voices
```

## Benchmark

Generate a production-style sample directly from the cached preset:

```bash
python backend/.bench/zero_shot_vieneu_test.py
```

Or benchmark the active backend API:

```bash
cd backend
python .bench/bench_vieneu.py
```

Default output:

- `backend/.bench/samples/vieneu/vieneu_0_3b_voice_default.wav`
- `backend/.bench/samples/vieneu/sample.wav`
- `backend/.bench/samples/benchmark.json`

## Validation status

Validated during this migration:

- `python backend/scripts/build_voice_default_preset.py --source-key voice_default --voice-key voice_default --device cpu`
- `python backend/.bench/zero_shot_vieneu_test.py`

## Notes

- `voice_2_clone` is kept only as a legacy alias in `clone-cache.json`
- persisted frontend state that still holds `voice_2_clone` is normalized to `voice_default`
- `GET /api/v1/system/tts?provider=vieneu` is the only supported TTS runtime query
