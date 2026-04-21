# web-app

React + Vite editor app for the manga recap workflow.

## Responsibilities

- Upload source chapter images
- Detect and edit panel regions in-browser
- Persist editor state and blobs with IndexedDB
- Send panel files to backend for Gemini script generation
- Hydrate returned `panelUnderstandings`, `storyMemories`, `timeline`, raw outputs, and logs
- Generate narration audio through backend `/api/v1/voice/*` routes

## Commands

```bash
npm install
npm run dev
npm run build
```

## Environment

Use `.env.example` and set:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_TTS_PROVIDER=vieneu
VITE_TTS_VOICE_KEY=default
```

Notes:
- `VITE_API_BASE_URL` is the active frontend setting for Step Script.
- Gemini API keys must be configured on the backend via `AI_BACKEND_GEMINI_API_KEY` in `backend/.env`.
- Voice presets are loaded from the backend via `GET /api/v1/voice/options`.
