export const MOTION_PRESETS = [
  "still_hold",
  "slow_zoom_in",
  "slow_zoom_out",
  "push_in_center",
  "pan_left",
  "pan_right",
  "pan_up",
  "pan_down",
  "handheld_tension",
  "impact_shake",
] as const;

export type MotionPreset = typeof MOTION_PRESETS[number];

export const TRANSITION_PRESETS = [
  "crossfade",
  "dip_to_black",
  "smooth_zoom_fade",
  "hard_cut",
] as const;

export type TransitionPreset = typeof TRANSITION_PRESETS[number];

export const SCENE_TYPES = [
  "establishing",
  "dialogue",
  "inner_thought",
  "mystery_reveal",
  "danger_build",
  "combat_action",
  "shock_reveal",
  "emotional_pause",
] as const;

export type SceneType = typeof SCENE_TYPES[number];

export const SCENE_MOODS = [
  "calm",
  "ominous",
  "tense",
  "violent",
  "tragic",
  "mystical",
  "lonely",
  "epic",
] as const;

export type SceneMood = typeof SCENE_MOODS[number];

export type SceneEffectMetadata = {
  sceneType?: SceneType;
  mood?: SceneMood;
  motionPreset?: MotionPreset;
  motionIntensity?: number;
  transition?: TransitionPreset;
  transitionDurationMs?: number;
  vfxTags?: string[];
  sfxTags?: string[];
  subtitleMood?: string;
};
