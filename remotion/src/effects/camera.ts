/**
 * Camera motion and timing utilities.
 *
 * Converts keyframe definitions from the video direction into
 * frame-level transform values for the scene image.
 */

import { interpolate, Easing } from "remotion";
import type { KeyframeEffect } from "../types/direction";

interface CameraTransform {
  scale: number;
  translateX: number;
  translateY: number;
}

const EASING_MAP: Record<string, (t: number) => number> = {
  linear: Easing.linear,
  ease_in: Easing.in(Easing.cubic),
  ease_out: Easing.out(Easing.cubic),
  ease_in_out: Easing.inOut(Easing.cubic),
};

/**
 * Compute the camera transform for a given frame within a scene.
 */
export function getCameraTransform(
  frame: number,
  totalFrames: number,
  keyframes: KeyframeEffect[],
  motionPreset: string,
): CameraTransform {
  const progress = totalFrames <= 1 ? 1 : frame / (totalFrames - 1);

  // If no keyframes, use the motion preset as a single effect
  const effects =
    keyframes.length > 0
      ? keyframes
      : [
          {
            time_pct: 0,
            effect: motionPreset,
            intensity: 0.7,
            easing: "ease_in_out",
            params: {},
          },
        ];

  // Accumulate transforms from all active effects
  let scale = 1;
  let translateX = 0;
  let translateY = 0;

  for (const kf of effects) {
    const easingFn = EASING_MAP[kf.easing] ?? EASING_MAP.ease_in_out;
    const intensity = Math.max(0, Math.min(1, kf.intensity));

    // Interpolate from keyframe start to end of scene
    const effectProgress = interpolate(progress, [kf.time_pct, 1], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: easingFn,
    });

    const result = applyEffect(kf.effect, effectProgress, intensity);
    scale *= result.scale;
    translateX += result.translateX;
    translateY += result.translateY;
  }

  return { scale, translateX, translateY };
}

function applyEffect(
  effect: string,
  progress: number,
  intensity: number,
): CameraTransform {
  const maxZoom = 0.08 * intensity;
  const maxPan = 40 * intensity;

  switch (effect) {
    case "zoom_in":
    case "push_in_center":
      return {
        scale: 1 + maxZoom * progress,
        translateX: 0,
        translateY: 0,
      };

    case "zoom_out":
    case "pull_back_reveal":
      return {
        scale: 1 + maxZoom * (1 - progress),
        translateX: 0,
        translateY: 0,
      };

    case "pan_left":
    case "drift_right_to_left":
      return {
        scale: 1 + maxZoom * 0.3,
        translateX: -maxPan * progress,
        translateY: 0,
      };

    case "pan_right":
    case "drift_left_to_right":
      return {
        scale: 1 + maxZoom * 0.3,
        translateX: maxPan * progress,
        translateY: 0,
      };

    case "pan_up":
    case "rise_up_focus":
      return {
        scale: 1 + maxZoom * 0.4,
        translateX: 0,
        translateY: -maxPan * progress,
      };

    case "pan_down":
    case "tilt_down":
      return {
        scale: 1 + maxZoom * 0.4,
        translateX: 0,
        translateY: maxPan * progress,
      };

    case "push_in_upper_focus":
      return {
        scale: 1 + maxZoom * progress,
        translateX: 0,
        translateY: -maxPan * 0.5 * progress,
      };

    case "push_in_lower_focus":
      return {
        scale: 1 + maxZoom * progress,
        translateX: 0,
        translateY: maxPan * 0.5 * progress,
      };

    case "ken_burns_tl":
      return {
        scale: 1 + maxZoom * progress,
        translateX: -maxPan * 0.6 * progress,
        translateY: -maxPan * 0.4 * progress,
      };

    case "ken_burns_br":
      return {
        scale: 1 + maxZoom * progress,
        translateX: maxPan * 0.6 * progress,
        translateY: maxPan * 0.4 * progress,
      };

    case "ken_burns_center":
      return {
        scale: 1 + maxZoom * 1.2 * progress,
        translateX: 0,
        translateY: 0,
      };

    case "parallax_depth":
      return {
        scale: 1 + maxZoom * 0.5 * progress,
        translateX: maxPan * 0.2 * Math.sin(progress * Math.PI),
        translateY: -maxPan * 0.15 * progress,
      };

    case "subtle_shake": {
      const shakeX = Math.sin(progress * Math.PI * 6) * 3 * intensity;
      const shakeY = Math.cos(progress * Math.PI * 4) * 2 * intensity;
      return {
        scale: 1,
        translateX: shakeX,
        translateY: shakeY,
      };
    }

    default:
      // Default: gentle push in
      return {
        scale: 1 + maxZoom * 0.5 * progress,
        translateX: 0,
        translateY: 0,
      };
  }
}

/**
 * Calculate the number of transition frames for a given duration.
 */
export function transitionFrames(durationMs: number, fps: number): number {
  return Math.round((durationMs / 1000) * fps);
}
