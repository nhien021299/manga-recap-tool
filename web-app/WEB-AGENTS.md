# Manga Recap Tool - AI Agent Guide

## System Role
This project is a full-web manga/webtoon recap tool.

Priorities:
- Browser-first architecture
- No giant canvas
- Desktop-first is acceptable
- Memory-safe image processing

---

## Core Principles

- Global coordinates are the source of truth
- Preview scale is never canonical
- Scene boxes are suggestions, not truth
- Extraction is deferred and intersection-based
- Heavy processing must not block the main thread

---

## Skill Routing

Automatically select the correct specialization:

### Image Processing
- Coordinates, mapping → virtual-strip-architect
- Scene detection → scene-detection-heuristics
- Performance, workers → image-worker-performance
- Extraction → extract-compositor
- Crop editing → crop-editor-ux

### React & App Architecture
- Structure, hooks, services → react-ts-clean-architect
- UI composition → react-ui-composition
- API flow → api-flow-orchestrator
- Refactor/review → react-clean-refactor-reviewer

### Design System
- Visual style → ui-art-direction
- Design consistency → design-system-guardian

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