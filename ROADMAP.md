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

## Checkpoint: VieNeu-TTS-0.3B Standard Migration (2026-04-22)

### Completed

- Replaced the old multi-provider TTS direction with one production TTS path only:
  - provider: `vieneu`
  - model: `pnnbao-ump/VieNeu-TTS-0.3B`
  - mode: `standard`
- Defined the canonical production preset:
  - `voice_default`
- Built a cached standard preset from the project reference wav/txt:
  - `backend/.models/vieneu-voices/voices.json`
  - `backend/.models/vieneu-voices/clone-cache.json`
- Switched backend generation to use cached preset data on every request:
  - no per-request reference encoding
  - `voice_default` is loaded once and reused
- Added preset build tooling for clean future setup:
  - [backend/scripts/build_voice_default_preset.py](./backend/scripts/build_voice_default_preset.py)
- Updated frontend defaults:
  - `VITE_TTS_PROVIDER=vieneu`
  - `VITE_TTS_VOICE_KEY=voice_default`
- Added migration compatibility for old saved clients:
  - `voice_2_clone -> voice_default`
  - `default -> voice_default`

### Removed From Active Product Scope

- `f5` provider and its backend runtime path
- F5 ONNX worker bridge and runtime worker code
- F5 setup instructions and F5 runtime references in the main docs
- VieNeu turbo preset flow as the active backend production path

## Active Product Decisions

- FE-BE structure stays active
- Step Script runs through backend Gemini
- Active script route stays `POST /api/v1/script/generate`
- Voice generation is backend-only
- The only supported TTS provider is `vieneu`
- The only supported TTS model is `VieNeu-TTS-0.3B`
- The only production voice preset is `voice_default`

## Active TTS Architecture

Backend voice contract:

- `GET /api/v1/voice/options`
- `POST /api/v1/voice/generate`
- `GET /api/v1/system/tts`

Production runtime behavior:

- backend loads `pnnbao-ump/VieNeu-TTS-0.3B` in `standard` mode
- backend loads cached preset data from `backend/.models/vieneu-voices/voices.json`
- each Step TTS request calls the model with the cached preset
- backend does not re-encode the reference clip for each request

Canonical project voice assets:

- source cache and reference:
  - `backend/.models/voice-cache/voice_default/source.mp3`
  - `backend/.models/voice-cache/voice_default/reference.wav`
  - `backend/.models/voice-cache/voice_default/reference.txt`
  - `backend/.models/voice-cache/voice_default/metadata.json`
- generated preset cache:
  - `backend/.models/vieneu-voices/voices.json`
  - `backend/.models/vieneu-voices/clone-cache.json`
  - `backend/.models/vieneu-voices/voice_default.wav`
  - `backend/.models/vieneu-voices/voice_default.txt`

## Current Milestones

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Architecture | Done | FE-BE structure is stable. |
| M1 Extract | Done | Browser-side upload/extract flow is active. |
| M2 Script | Done | Backend Gemini route is the active product path. |
| M3 Voice | Done | Production TTS is standardized on `VieNeu-TTS-0.3B` with cached preset `voice_default`. |
| M4 Timeline | In Progress | Timeline editing remains in active development. |
| M5 Render | Not started | Browser render/export is still pending. |

## Key Conclusions

1. The repo should expose one TTS path only: `vieneu + voice_default`.
2. `voice_default` must be treated as a cached preset, not a per-request zero-shot clone.
3. The correct setup workflow is:
   - prepare `reference.wav` and `reference.txt`
   - build preset once
   - reuse the cached preset in every request
4. Backend and frontend defaults must stay aligned on `voice_default`.

## Next Actions

1. Keep all new TTS work aligned with `VieNeu-TTS-0.3B standard`.
2. Rebuild `voice_default` only when the project decides to replace the canonical reference voice.
3. Keep README and setup steps synchronized with the preset builder script.
4. Continue product work on timeline editing and final render/export.

## Open Risks

- Rebuilding `voice_default` from a different reference clip will change the production narration voice for the whole product.
- The repo currently still contains some legacy local assets until final cleanup of developer machines is complete.
- `VieNeu-TTS-0.3B` standard mode depends on a full Python environment with `torch`, `torchaudio`, `transformers`, `neucodec`, and `vieneu`.
