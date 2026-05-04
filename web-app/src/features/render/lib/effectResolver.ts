import {
  MOTION_PRESETS,
  TRANSITION_PRESETS,
  type SceneEffectMetadata,
  type SceneType,
  type SceneMood,
} from "./effectSchema";

const DEFAULT_RENDER_EFFECTS = {
  transition: "crossfade",
  transitionDurationMs: 550,
  motionPreset: "push_in_center",
  motionIntensity: 0.6,
  vfxTags: [],
  sfxTags: [],
} as const;

const SCENE_MOTION_DEFAULTS: Record<SceneType, any> = {
  establishing: {
    motionPreset: "slow_zoom_out",
    motionIntensity: 0.5,
    transition: "crossfade",
    transitionDurationMs: 650,
    vfxTags: ["film_grain"],
  },
  dialogue: {
    motionPreset: "still_hold",
    motionIntensity: 0.35,
    transition: "crossfade",
    transitionDurationMs: 500,
    vfxTags: ["film_grain"],
  },
  inner_thought: {
    motionPreset: "slow_zoom_in",
    motionIntensity: 0.5,
    transition: "dip_to_black",
    transitionDurationMs: 600,
    vfxTags: ["film_grain", "dust"],
  },
  mystery_reveal: {
    motionPreset: "push_in_center",
    motionIntensity: 0.7,
    transition: "smooth_zoom_fade",
    transitionDurationMs: 550,
    vfxTags: ["film_grain", "edge_glow"],
  },
  danger_build: {
    motionPreset: "slow_zoom_in",
    motionIntensity: 0.8,
    transition: "dip_to_black",
    transitionDurationMs: 500,
    vfxTags: ["film_grain", "dark_smoke"],
  },
  combat_action: {
    motionPreset: "handheld_tension",
    motionIntensity: 0.9,
    transition: "hard_cut",
    transitionDurationMs: 250,
    vfxTags: ["film_grain", "speed_lines"],
  },
  shock_reveal: {
    motionPreset: "impact_shake",
    motionIntensity: 0.95,
    transition: "smooth_zoom_fade",
    transitionDurationMs: 300,
    vfxTags: ["film_grain", "color_pulse"],
  },
  emotional_pause: {
    motionPreset: "slow_zoom_out",
    motionIntensity: 0.35,
    transition: "crossfade",
    transitionDurationMs: 700,
    vfxTags: ["film_grain", "dust"],
  },
};

const MOOD_INTENSITY_MODIFIER: Partial<Record<SceneMood, number>> = {
  calm: -0.15,
  lonely: -0.1,
  tragic: -0.05,
  mystical: 0.08,
  ominous: 0.12,
  tense: 0.18,
  violent: 0.22,
  epic: 0.18,
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function isValidMotionPreset(value?: string) {
  return !!value && MOTION_PRESETS.includes(value as any);
}

// Map legacy transition names to new presets
const TRANSITION_COMPAT: Record<string, string> = {
  flash_cut: "smooth_zoom_fade",
  blur_fade: "smooth_zoom_fade",
  fade_white: "smooth_zoom_fade",
  fade_black: "dip_to_black",
  cut: "hard_cut",
};

function isValidTransition(value?: string) {
  if (!value) return false;
  return TRANSITION_PRESETS.includes(value as any) || value in TRANSITION_COMPAT;
}

function normalizeTransition(value: string): string {
  return TRANSITION_COMPAT[value] ?? value;
}

export function resolveSceneEffects(input: SceneEffectMetadata = {}) {
  const sceneDefaults = input.sceneType && SCENE_MOTION_DEFAULTS[input.sceneType]
    ? SCENE_MOTION_DEFAULTS[input.sceneType]
    : ({} as any);

  const merged = {
    ...DEFAULT_RENDER_EFFECTS,
    ...sceneDefaults,
    ...input,
  } as const;

  const moodModifier = input.mood
    ? MOOD_INTENSITY_MODIFIER[input.mood] ?? 0
    : 0;

  const motionIntensity = clamp(
    Number((merged as any).motionIntensity ?? DEFAULT_RENDER_EFFECTS.motionIntensity) + moodModifier,
    0.1,
    1.0
  );

  return {
    transition: isValidTransition((merged as any).transition)
      ? normalizeTransition((merged as any).transition)
      : DEFAULT_RENDER_EFFECTS.transition,

    transitionDurationMs: clamp(
      Number((merged as any).transitionDurationMs ?? DEFAULT_RENDER_EFFECTS.transitionDurationMs),
      180,
      800
    ),

    motionPreset: isValidMotionPreset((merged as any).motionPreset)
      ? (merged as any).motionPreset
      : DEFAULT_RENDER_EFFECTS.motionPreset,

    motionIntensity,

    vfxTags: Array.isArray((merged as any).vfxTags) ? (merged as any).vfxTags : [],
    sfxTags: Array.isArray((merged as any).sfxTags) ? (merged as any).sfxTags : [],
    subtitleMood: (merged as any).subtitleMood ?? input.mood ?? "default",
  };
}
