# web-app

React + Vite editor app for the manga recap workflow.

## Responsibilities

- Upload source chapter images
- Detect and edit panel regions in-browser
- Persist editor state and blobs with IndexedDB
- Submit extracted panels to `ai-backend`
- Poll script jobs and merge results back into timeline state
- Keep voice generation frontend-side for now

## Commands

```bash
npm install
npm run dev
npm run build
```

## Environment

Use `.env.example` and set:

```bash
VITE_API_BASE_URL=http://localhost:8000
```
