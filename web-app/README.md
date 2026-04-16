# web-app

React + Vite editor app for the manga recap workflow.

## Responsibilities

- Upload source chapter images
- Detect and edit panel regions in-browser
- Persist editor state and blobs with IndexedDB
- Send panel files to backend for Gemini script generation
- Hydrate returned `panelUnderstandings`, `storyMemories`, `timeline`, raw outputs, and logs
- Keep voice generation frontend-side with ElevenLabs

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
VITE_GEMINI_API_KEY=
VITE_ELEVENLABS_API_KEY=
VITE_TTS_VOICE_ID=pNInz6obpgmqS29pXo3W
VITE_TTS_MODEL=eleven_multilingual_v2
```

Notes:
- `VITE_API_BASE_URL` is the active frontend setting for Step Script.
- `VITE_GEMINI_API_KEY` is only a temporary backend fallback source if `AI_BACKEND_GEMINI_API_KEY` is not set.
