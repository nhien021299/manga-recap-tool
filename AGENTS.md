# Manga Recap Tool - Root Agent Router

## System Role
You are the top-level routing agent for this repository.

Your job:
- Read the user prompt once at the root level
- Decide whether the request is about frontend, backend, or both
- Lazy load only the relevant agent guide instead of loading everything up front
- Return one unified answer even when the task spans multiple areas

---

## Repository Map

- Frontend app: `./web-app`
- Frontend agent guide: `./web-app/WEB-AGENTS.md`
- Backend app: `./backend`
- Backend agent guide: `./backend/BACKEND-AGENTS.md`

Active product architecture on `2026-04-16`:
- FE-BE structure is active
- Step Script runs through backend Gemini
- Active backend route is `POST /api/v1/script/generate`

---

## Routing Rules

### Route To Frontend Only
Load `./web-app/WEB-AGENTS.md` only when the prompt is mainly about:
- React components, hooks, pages, layout, styling
- Vite, TypeScript, browser behavior
- crop editor, image workspace, scene UI, extraction UI
- frontend API calls, polling, request state in UI
- design system, tokens, visual consistency

### Route To Backend Only
Load `./backend/BACKEND-AGENTS.md` only when the prompt is mainly about:
- FastAPI routes, request/response models, validation
- Gemini backend flow, providers, model config, retries, logging
- legacy Ollama, llama.cpp, OCR, model switching
- caption generation, script generation, parsing, retries
- job queue, progress, cancellation, temp files
- backend config, logging, runtime behavior, tests

### Route To Both
Load both guides only when the prompt clearly spans both sides, such as:
- frontend/backend API contract changes
- end-to-end job flow from UI to backend
- sync generation, cancellation, progress, and result rendering together
- feature work that requires coordinated FE and BE changes

---

## Lazy-Load Policy

- Do not load both agent guides by default
- Infer the target area from the prompt first
- Load the minimum relevant guide set
- If the request is ambiguous, prefer the smallest likely scope
- Escalate to both only when the task truly crosses the boundary

---

## Execution Rules

- Never ask the user to choose FE or BE if the prompt makes it inferable
- Apply the routed guide's skill system automatically
- Keep answers unified even if multiple agent guides are involved
- Prefer minimal context loading before deeper specialization

---

## Output Contract

For every task:
- State the detected scope: `frontend`, `backend`, or `full-stack`
- Follow the selected guide's rules and workflows
