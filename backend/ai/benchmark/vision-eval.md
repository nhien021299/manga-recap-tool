# Vision Model Benchmark Guide
> Manga Recap Tool - Legacy Local-AI Evaluation Reference

> [!WARNING]
> This document is not the active Step Script product flow.
> The active product path on `2026-04-16` is backend Gemini via `POST /api/v1/script/generate`.
> Use this file only when explicitly evaluating or archiving legacy local-AI vision paths.

## Purpose

This guide describes how to benchmark legacy local vision/caption models for reference work.
It exists to support forensic analysis, historical comparison, or deliberate local-runtime experiments.

## Legacy benchmark goals

Evaluate candidate local models on:
- visual fidelity
- OCR and SFX extraction
- usefulness of panel understanding for downstream script generation
- runtime cost on real chapter workloads

## Example legacy candidates

- `qwen2.5vl:7b`
- `qwen3-vl:4b`
- `gemma3:latest`

## Legacy benchmark environment

Use local-AI settings only when the task explicitly targets those paths:

```env
AI_BACKEND_CAPTION_CHUNK_SIZE=1
AI_BACKEND_CAPTION_MAX_TOKENS=512
AI_BACKEND_VISION_TIMEOUT_SECONDS=60
AI_BACKEND_VISION_TIMEOUT_RETRIES=2
AI_BACKEND_VISION_MAX_WIDTH=768
AI_BACKEND_VISION_MAX_HEIGHT=1536
```

## Example legacy run

```powershell
python semi_auto_caption_benchmark.py `
  --images "D:\Manhwa Recap\Chapter 1 cropped" `
  --models qwen2.5vl:7b qwen3-vl:4b gemma3:latest `
  --output ".\benchmark_out"
```

## Legacy scoring dimensions

- specificity of visual description
- action clarity
- emotional accuracy
- dialogue and OCR fidelity
- hallucination rate
- throughput per chapter

## Legacy runtime targets

| Panels | Target |
| --- | --- |
| 10 | < 20s |
| 30 | < 60s |
| 60 | < 120s |

## Decision note

Do not treat a passing result here as a product decision by itself.
The active product direction is backend Gemini unless a future task explicitly reopens local-AI runtime work.
