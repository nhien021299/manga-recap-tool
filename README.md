# manga-recap-tool

Monorepo layout:

- `web-app/`: React + Vite editor, browser-first image workflow, IndexedDB session persistence.
- `ai-backend/`: FastAPI job backend for local caption + script generation with pluggable providers.
- `ai/`: project notes, roadmap, and internal planning docs.

## Current M2 status

- Frontend and backend local flow is wired and working end-to-end.
- Backend runtime for caption + script jobs is stable enough for real chapter runs after timeout / retry hardening.
- Current quality bottleneck is the vision caption stage, not the queue / polling / runtime path.
- Default local `gemma3` setup is usable for debugging and stability checks, but may be too weak for accurate manga-panel understanding on real chapters.

## Web app

```bash
cd web-app
npm install
npm run dev
```

Default frontend API target: `http://localhost:8000`.

From repo root you can also run:

```bash
npm run dev:web
```

## AI backend

For first-time setup:
```bash
cd ai-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For later runs:
```bash
cd ai-backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health checks:

- `http://localhost:8000/api/v1/health`
- `http://localhost:8000/api/v1/system/providers`

## Backend config notes

`ai-backend/.env.example` now includes the current local-debug defaults for M2:

- caption chunk size reduced to `1`
- vision timeout / retry controls
- image resize controls for vision preprocessing
- script validation / retry controls

Important:

- The caption stage now uses a visual-only prompt to reduce lore leakage.
- Story context is intended to influence the script stage, not the raw caption stage.
- If output is still too generic, the next likely improvement is a stronger vision model rather than more timeout tuning.

Suggested local vision models to benchmark next:

- `qwen2.5vl`
- `llama3.2-vision`
- `gemma3:12b` if your hardware can handle it
