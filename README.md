# manga-recap-tool

Frontend-backend manga recap editor.

## Repo layout

- `web-app/`: React + Vite editor for upload, extract, script, voice, and render flow
- `ai-backend/`: FastAPI service for Step Script generation
- `ai/`: notes and internal references

## Current architecture

- Upload and extract stay browser-side
- Step Script sends extracted panel files from frontend to backend
- Backend runs Gemini in 2 stages:
  - panel understanding
  - narration generation with chunk continuity
- Frontend hydrates `panelUnderstandings`, `storyMemories`, `timeline`, raw outputs, and logs
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

Temporary fallback also works:

```bash
VITE_GEMINI_API_KEY=
```

If `AI_BACKEND_GEMINI_API_KEY` is empty, backend can read `VITE_GEMINI_API_KEY` from `web-app/.env`.

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
```

## Validation status

Verified on `2026-04-16`:
- `npm run build:web` passes
- backend import passes after dependency install
- backend Gemini smoke test passes through `POST /api/v1/script/generate`

## Open risks

- Real chapter validation on `10` and `52` panel workloads is still pending
- Backend Gemini route is synchronous and cannot be cancelled mid-request
- Legacy local-AI backend modules still exist in the repo but are not part of the active product flow
