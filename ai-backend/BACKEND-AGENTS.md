# Manga Recap Tool - AI Backend Agent Guide

## System Role
This project is the AI backend for a manga/webtoon recap tool.

Priorities:
- API-first backend architecture
- Provider-agnostic AI integration
- Predictable async job execution
- Safe temp-file and image handling

---

## Core Principles

- API contracts are the source of truth
- Provider selection must stay swappable
- Long-running generation belongs in the job pipeline
- Cancellation and cleanup are mandatory, not optional
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
