# Manga Recap Tool - AI Backend Agent Guide

## System Role
This project is the AI backend for a manga/webtoon recap tool.

Current active product flow on `2026-04-16`:
- Step Script runs through backend Gemini
- Active entrypoint is `POST /api/v1/script/generate`
- Legacy Ollama / llama.cpp / OCR / async job queue code still exists in the repo, but is not the active Step Script product path

Priorities:
- API-first backend architecture
- Provider-agnostic AI integration
- Predictable request execution
- Safe temp-file and image handling

---

## Core Principles

- API contracts are the source of truth
- Provider selection must stay swappable
- Cleanup is mandatory, whether execution is sync or async
- Treat async job orchestration as optional unless the active route requires it
- Raw AI output must be normalized before leaving the service layer

---

## Skill Routing

Automatically select the correct specialization:

### Backend Architecture
- FastAPI structure, dependencies, lifecycle -> fastapi-service-architect
- Route contracts, request/response schemas -> route-contract-guardian
- Refactor, maintainability review -> python-backend-refactor-reviewer

### AI Pipeline
- Provider selection, adapters, model switching -> provider-abstraction-engineer
- Caption understanding, panel/image processing -> vision-caption-pipeline
- Script generation, structured outputs, memory flow -> script-generation-orchestrator

### Runtime & Operations
- Queueing, cancellation, progress, concurrency -> async-job-queue-specialist
- Config, logging, temp files, observability -> config-observability-guardian

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

For backend runtime and service quality:
- ./ai/backend-rules.md
