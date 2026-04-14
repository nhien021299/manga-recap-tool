# manga-recap-tool

Monorepo layout:

- `web-app/`: React + Vite editor, browser-first image workflow, IndexedDB session persistence.
- `ai-backend/`: FastAPI job backend for local caption + script generation with pluggable providers.
- `ai/`: project notes, roadmap, and internal planning docs.

## Web app

```bash
cd web-app
npm install
npm run dev
```

Default frontend API target: `http://localhost:8000`.

## AI backend

```bash
cd ai-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
