# Manga Recap Tool - Execution Roadmap

## Overview

This document defines the execution plan for building the web-based manga/webtoon recap tool.

Goals:
- Full web app (no backend for now)
- Memory-safe image processing
- Clean React + TypeScript architecture
- End-to-end pipeline: Upload -> Extract -> Script -> Voice -> Timeline -> Render

## System Principles

- Global coordinates are the source of truth.
- Preview scale is never canonical.
- Scene boxes are suggestions, not truth.
- Extraction is deferred and intersection-based.
- Avoid giant canvas usage.
- Heavy processing must not block the main thread.
- UI must follow the "Midnight Studio" design system.

## Milestone Overview

| Milestone | Name |
| --- | --- |
| M0 | Stabilize Architecture |
| M1 | Extract System Hardening |
| M2 | Script Integration |
| M3 | Voice / TTS |
| M4 | Timeline System |
| M5 | Video Render MVP |

## Progress Snapshot (April 14, 2026)

### Current status
- Active milestone: `M1 - Extract System Hardening`.
- M1 is in progress, with major UX and extraction-flow improvements already implemented in `StepExtract.tsx`.
- Build status after latest updates: `npm run build` passes.

### Completed recently (Extract step)
- Rebalanced workspace layout to prioritize crop viewport (`md: 74/26`, `lg: 76/24`).
- Moved `Locate` + `Add` scene actions from scene list header into crop panel controls.
- Added `Export to` button in scene list header with progress indicator.
- Implemented folder export flow using directory picker + write cropped images as sequential PNG files.
- Added prepared-panels cache keyed by extraction state to avoid re-cropping when continuing to next step.
- Separated loading state between `Continue` and `Export to` so export no longer triggers continue-button loading animation.
- Enlarged control clusters in crop panel (`zoom`, `Locate`, `Add`, `Export to`) for better usability.
- Fixed control overlap by increasing vertical offset between top-right toolbars.
- Fixed inverted mouse-wheel behavior in scene list scroll container.

### M1 task mapping update
- Scene editor UX:
  - Done: resize/move/delete/add manual scene.
  - Done: locate current scene in list.
  - In progress: merge/split, keyboard nudge, explicit clear-selection action.
- Extract output pipeline:
  - Done: crop and panel generation flow.
  - Done: export to user-selected folder.
  - Done: panel reuse for next step without duplicate loading.
- Persistence:
  - Done: panels saved in IndexedDB via store.
  - In progress: stricter invalidation rules and full resume validation across all step transitions.

## M0 - Stabilize Architecture

### Goal
Build a clean foundation before adding new features.

### Tasks

1. Folder structure (gradual refactor)

```text
src/
  app/
  shared/
  features/
    upload/
    extract/
    script/
    voice/
    timeline/
    render/
  store/
  workers/
  types/
```

2. Separate logic from components
- Refactor `StepUpload.tsx` into:
- `useUploadProcessing()`
- `extractSceneSuggestions()`
- coordinate and mapping helpers

3. Define core types

```ts
type SourceImage = unknown
type SceneSuggestion = unknown
type ExtractedPanel = unknown
type ScriptSegment = unknown
type VoiceClip = unknown
type TimelineItem = unknown
type RenderJob = unknown
```

4. Standard async state

```ts
type AsyncState<T> = {
  status: "idle" | "loading" | "success" | "error"
  data: T | null
  error: string | null
}
```

### Definition of Done

- No heavy logic inside UI components.
- Types are clearly defined.
- Worker logic is isolated.
- Architecture is stable.

## M1 - Extract System Hardening (Most Important)

### Goal
Make Extract production-ready.

### Tasks

1. Scene detection improvement
- Add overlap detection (bottom A + top B).
- Add scoring system.
- Add merge/split suggestion logic.

2. Extract editor UX
- Resize handles (top/bottom)
- Merge scenes
- Split scenes
- Add manual scene
- Delete scene
- Keyboard nudge
- Clear selection state

3. Extract output pipeline

```ts
type ExtractedPanel = {
  id: string
  sceneId: string
  blobKey: string
  width: number
  height: number
  orderIndex: number
}
```

4. Persistence
- Store panels in IndexedDB.
- Resume session after refresh.
- Invalidate when new upload happens.

### Definition of Done

- Extract works across multiple images.
- Scene editing is stable.
- Output panels are reusable.
- No crashes on large chapters.

## M2 - Script Integration

### Goal
Create a stable contract between Extract and Script.

### Tasks

1. Script source model

```ts
type ScriptSourceUnit = {
  panelId: string
  orderIndex: number
}
```

2. Script layers
- Raw LLM output
- Normalized script
- Editable UI state

3. Editing model

```ts
type ScriptSegment = {
  narration: string
  status: "auto" | "edited"
}
```

4. Invalidation strategy
- When panels change, mark script as outdated.
- Do not delete user edits immediately.

### Definition of Done

- Script is tied to `panelId`.
- Script is editable and stable.
- Regeneration is possible.

## M3 - Voice / TTS

### Goal
Generate and preview voice per panel.

### Tasks

1. Voice model

```ts
type VoiceClip = {
  panelId: string
  text: string
  blobKey: string
  durationMs: number
  status: "idle" | "generating" | "ready"
}
```

2. TTS service layer
- Separate API client.
- Separate mapping.
- Separate orchestration.

3. StepVoice UI features
- Generate one / all
- Play preview
- Retry
- Error state

4. Storage
- Store audio blobs in IndexedDB.
- Store metadata in Zustand.

### Definition of Done

- Voice per panel works.
- Batch generation works.
- Audio persists.

## M4 - Timeline System

### Goal
Define playback order and duration.

### Tasks

1. Timeline model

```ts
type TimelineItem = {
  panelId: string
  imageKey: string
  audioKey?: string
  startMs: number
  durationMs: number
}
```

2. Duration logic
- With audio: use audio duration.
- Without audio: use fallback duration.

3. Timeline UI
- Reorder
- Preview total duration
- Validate items

### Definition of Done

- Timeline is auto-generated.
- User can adjust timeline.
- Timeline is ready for rendering.

## M5 - Video Render MVP

### Goal
Export MP4 in the browser.

### Tasks

1. Prepare assets
- Load panels.
- Load audio.
- Create temporary workspace.

2. FFmpeg pipeline
- Combine images.
- Combine audio.
- Generate MP4.

3. Minimal features
- No complex animation.
- Optional fade only.

### Definition of Done

- Video export works.
- Audio sync is correct.
- Output file is downloadable.

## UI System

### Theme
- Midnight Studio

### Rules
- Dark-first UI
- Minimal noise
- One accent color
- Image-first layout
- Clean spacing
- No heavy gradients
- No glassmorphism

## Tech Stack Rules

### State
- Zustand -> editor state
- React Query (optional) -> server state

### Storage
- IndexedDB -> blobs
- localStorage -> config

### Processing
- Web Workers
- OffscreenCanvas
- No giant canvas

## Development Order

1. Phase 1: M0 + M1
2. Phase 2: M2 + M3
3. Phase 3: M4 + M5

## Final Flow

1. Upload images
2. Detect scenes
3. Edit scenes
4. Extract panels
5. Generate script
6. Edit script
7. Generate voice
8. Build timeline
9. Export video

## Priority Note

If only one milestone can be done next, do `M1 (Extract System Hardening)` because all later milestones depend on it.
