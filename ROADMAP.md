# Manga Recap Tool - Executive Roadmap

## Current State

Repo is active as a frontend-backend product:

```text
manga-recap-tool/
|- web-app/
|- backend/
|- ai/
`- ROADMAP.md
```

- `web-app/`: upload, extract, script, voice, and render UI
- `backend/`: FastAPI service for Step Script generation and backend-owned TTS
- `ai/`: notes and internal references

Verified on `2026-04-21`:

- `npm --prefix web-app run build` passes
- `pytest backend/tests/test_voice_routes.py backend/tests/test_routes.py` passes
- `python -m compileall backend/app backend/tests` passes

## Checkpoint: TTS Cleanup, Preset Preview, and F5 Reality Check (2026-04-21)

### Completed

- Removed old TTS branches from the active repo path:
  - `dia`
  - `piper`
  - legacy ElevenLabs browser path
- Kept the active backend TTS contract on:
  - `GET /api/v1/voice/options`
  - `POST /api/v1/voice/generate`
  - `GET /api/v1/system/tts`
- Locked the active provider set to:
  - `vieneu`
  - `f5`
- Added runtime-specific diagnostics so `vieneu` and `f5` can be checked separately through:
  - `GET /api/v1/system/tts?provider=vieneu`
  - `GET /api/v1/system/tts?provider=f5`
- Added curated preset metadata and frontend preview playback for TTS voice presets.
- Generated sample preview WAV files for both providers and mounted them as backend static assets for the frontend voice picker.

### Current Progress

- `vieneu`
  - backend generation flow is working
  - frontend preview/sample flow is working
  - short Vietnamese preview samples under 10 seconds were regenerated and are usable
- `f5`
  - ONNX worker runtime is working
  - DirectML GPU path is detectable and usable on the current machine
  - preset reference flow is wired
  - frontend preview/sample flow is wired
  - benchmark/sample generation works mechanically end to end

### Important Remaining Issue

- `f5` is still not production-ready for Vietnamese narration quality.
- The current ONNX text pipeline in [backend/runtime/f5/f5_onnx_worker.py](./backend/runtime/f5/f5_onnx_worker.py) does not preserve Vietnamese text faithfully:
  - Vietnamese diacritics are normalized poorly
  - generated phoneme/token behavior is unstable
  - output can keep the cloned voice color but still sound unnatural or non-human for Vietnamese reading
- In practice:
  - reference WAV files under `backend/.models/f5-reference` can sound fine because they are real source audio
  - generated sample WAV files under `backend/.bench/samples/f5` can still sound wrong because the text-to-speech stage is where the failure happens

### Product Conclusion Right Now

- `vieneu` is the only usable default for actual Vietnamese recap narration right now.
- `f5` should still be treated as an experimental comparison path, not a user-trusted production voice path.

## Active Product Decisions

- FE-BE structure stays active
- Step Script runs through backend Gemini
- Active script route stays `POST /api/v1/script/generate`
- Voice generation is backend-only
- Default TTS path is `vieneu`
- Secondary TTS path is `f5` for runtime comparison and benchmarking

## Active TTS Architecture

Backend voice contract:

- `GET /api/v1/voice/options`
- `POST /api/v1/voice/generate`
- `GET /api/v1/system/tts`

TTS provider behavior:

- `vieneu`
  - default provider
  - CPU-first
  - exposed to frontend as the default preset flow
- `f5`
  - ONNX worker provider
  - supports `cpu` or `gpu` runtime selection through `AI_BACKEND_TTS_RUNTIME`
  - uses local reference WAV/TXT presets

Diagnostics:

- `GET /api/v1/system/tts?provider=vieneu`
- `GET /api/v1/system/tts?provider=f5`

## Current Milestones

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | Done | FE-BE structure is stable. |
| M1 Extract | Done | Browser-side upload/extract flow is active. |
| M2 Script | Done | Backend Gemini route is the active product path. |
| M3 Voice | Done | Vieneu & F5 presets overhauled with authentic manga recap narration personas. F5 reference text duplication fixed. Static mount race condition resolved. Fresh samples regenerated. |
| M4 Timeline | In Progress | Timeline editing remains in active development. |
| M5 Render | Not started | Browser render/export is still pending. |

## Next Actions

1. Keep `vieneu` as the only trusted default for Vietnamese recap voice until a better `f5` text pipeline exists.
2. Decide whether `f5` should stay visible in the frontend or be hidden behind an experimental toggle.
3. If `f5` stays, replace the current Vietnamese text normalization/token path with one that is actually compatible with Vietnamese reading.
4. Continue hardening the frontend voice UX around preview, preset selection, and per-line generation using the stable `vieneu` path.
5. Continue hardening the Gemini path with real chapter-scale evaluation.

## Open Risks

- `f5` still depends on correct local bundle placement and good reference clips.
- `f5` can generate mechanically valid WAV output that still sounds wrong for Vietnamese, which is worse than a hard runtime failure because it can look successful while being unusable.
- DirectML availability is machine-dependent and must be confirmed through `/api/v1/system/tts?provider=f5`.
- Script generation remains synchronous and cannot be cancelled mid-request.
