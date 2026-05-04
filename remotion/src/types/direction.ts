/**
 * TypeScript types matching the Python VideoDirection models.
 * These are the input props for the Remotion composition.
 */

export interface KeyframeEffect {
  time_pct: number; // 0.0 - 1.0
  effect: string;
  intensity: number; // 0.0 - 1.0
  easing: string;
  params: Record<string, unknown>;
}

export interface SceneTransition {
  type: string;
  duration_ms: number;
  params: Record<string, unknown>;
}

export interface TextOverlay {
  text: string;
  start_pct: number;
  end_pct: number;
  style: "subtitle" | "subtitle_stroke" | "dialogue_bubble" | "title_card";
  position: string;
}

export interface SceneDirection {
  scene: number;
  total_duration_ms: number;
  audio_start_ms: number;
  keyframes: KeyframeEffect[];
  transition_in: SceneTransition | null;
  transition_out: SceneTransition;
  text_overlays: TextOverlay[];
  color_grade: string;
  motion_preset: string;
  scene_type?: string;
  mood?: string;
  motion_intensity?: number;
  transition?: string;
  transition_duration_ms?: number;
  vfx_tags?: string[];
  sfx_tags?: string[];
  subtitle_mood?: string;
}

export interface SceneAsset {
  scene: number;
  title: string;
  imagePath: string | null;
  audioPath: string | null;
  dialogueAudioPath: string | null;
  audioDurationMs: number;
  dialogueDurationMs: number | null;
}

export interface VideoDirectionProps {
  chapter: number;
  total_duration_ms: number;
  fps: number;
  width: number;
  height: number;
  scenes: SceneDirection[];
  assets: SceneAsset[];
  publicDir: string;
  global_settings: Record<string, unknown>;
}
