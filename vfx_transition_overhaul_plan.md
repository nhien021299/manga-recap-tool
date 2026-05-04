# Plan: VFX + Transition Overhaul

## Issue Analysis

### 1. Bottom blur artifact
- SceneImage.tsx already has a blurred background fill (`blur(30px) brightness(0.3)`)
- But when `colorFilter` is applied, it can create an inconsistent effect
- The vignette `radial-gradient` is also adding dark edges that interact badly with the blur
- **Fix**: Clean up the blur bg + vignette layering

### 2. Audio cut at scene transitions
- `calculateSceneTiming` overlaps scenes by `transOutMs` frames
- This means the **next scene starts playing** while the current scene is still fading out
- Audio from current scene gets muted as opacity → 0
- **Root cause**: transition overlap eats into audio time
- **Fix**: Ensure audio is NOT affected by opacity transitions (audio should play full duration)

### 3. Transition redesign
Current transitions are "amateur": white flash, blur pop, etc.
Professional manhwa recap channels use:
- **crossfade** (90% of transitions) — simple, elegant
- **dip_to_black** (dramatic pauses only) — slow, intentional
- **hard_cut** (fast action) — instant, no frills

**Remove**: `flash_cut` (cheesy), `blur_fade` (gimmicky)
**Replace with**: `smooth_zoom_fade` — crossfade + subtle scale shift

### 4. VFX System (Code-only, CSS + Remotion)
Planned effects:
- **Film grain** — animated noise texture overlay
- **Vignette** — already exists, improve
- **Letterbox** — cinematic black bars for dramatic moments
- **Atmospheric particles** — rain, dust, embers
- **Color pulse** — subtle color intensity beat on dramatic moments
- **Edge glow** — soft light bloom on edges

## Execution Order

1. Fix SceneImage blur background
2. Fix audio continuity across transitions  
3. Redesign transitions (simple, cinematic)
4. Implement VFX system
5. Wire VFX into effectResolver + Remotion pipeline
