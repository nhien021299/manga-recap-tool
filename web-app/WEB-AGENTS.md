# Manga Recap Tool - Frontend Agent Guide

## System Role
This frontend is the editor and orchestration layer for a manga/webtoon recap tool.

Current active product flow on `2026-04-22`:
- Upload and extraction stay browser-side
- Step Script sends extracted panel files to the backend Gemini route
- Step Voice calls backend-owned VieNeu TTS routes
- Timeline editing and clip state live in the frontend store
- Browser FFmpeg export is active as the current export path
- Official final export is moving toward backend-native rendering with browser export kept as fallback/preview

Priorities:
- Browser-first for ingest, extraction, editing, and preview
- Backend-assisted for AI generation and TTS
- Export-path aware architecture, with parity between browser fallback and official backend render where possible
- No giant canvas
- Desktop-first is acceptable
- Memory-safe media processing

---

## Core Principles

- Global coordinates are the source of truth
- Preview scale is never canonical
- Scene boxes are suggestions, not truth
- Extraction is deferred and intersection-based
- Heavy image processing must not block the main thread
- Frontend state is the source of truth for timeline ordering, render intent, and user edits
- UI components should not own backend contract details
- Browser render is a working fallback path, not a reason to leak render complexity into unrelated UI code

---

## Skill Routing

Automatically select the correct specialization:

### Image Processing
- Coordinates, mapping -> virtual-strip-architect
- Scene detection -> scene-detection-heuristics
- Performance, workers -> image-worker-performance
- Extraction -> extract-compositor
- Crop editing -> crop-editor-ux

### React & App Architecture
- Structure, hooks, services -> react-ts-clean-architect
- UI composition -> react-ui-composition
- API flow -> api-flow-orchestrator
- Refactor/review -> react-clean-refactor-reviewer

### Render & Export
- Timeline compilation, export orchestration, FFmpeg lifecycle -> react-ts-clean-architect
- Progress, error surfacing, preview/result flow -> api-flow-orchestrator
- Motion design, editor-facing export UX -> react-ui-composition + ui-art-direction

### Design System
- Visual style -> ui-art-direction
- Design consistency -> design-system-guardian

---

## Render / Export Rules

- Treat the compiled render plan as the frontend source of truth for clip order, duration, caption mode, and motion metadata.
- Keep render preparation, render execution, and preview/result handling separated from screen components.
- Do not let render components assemble raw backend contracts inline; use dedicated helpers or API modules.
- Surface render phases, progress, and actionable failures explicitly. Never collapse all failures into a generic `Render failed`.
- Clean up temporary browser render assets aggressively to avoid WASM FS and memory blowups.
- Keep browser export deterministic for the same timeline input.
- If browser fallback and backend official export coexist, keep behavior aligned at the render-plan level instead of duplicating timeline logic in two places.
- Voice preview or voice-option polling must not block export progress or poison the export UI with unrelated failures.

---

## Execution Rules

- Never ask user to choose a skill
- Infer and apply skills automatically
- Combine multiple skills when needed
- Return a unified final answer

---

## Project Rules

Follow:
- ./ai/project-rules.md

For UI:
- ./ai/design-rules.md
