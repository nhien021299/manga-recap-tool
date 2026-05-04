import { interpolate } from "remotion";
import type { MotionPreset } from "./effectSchema";

type ResolveMotionArgs = {
  frame: number;
  durationInFrames: number;
  preset: MotionPreset;
  intensity: number;
};

export function resolveMotionStyle({
  frame,
  durationInFrames,
  preset,
  intensity,
}: ResolveMotionArgs): React.CSSProperties {
  const safeDuration = Math.max(durationInFrames, 1);
  const progress = frame / safeDuration;

  const zoomSmall = 1 + 0.025 * intensity;
  const zoomMedium = 1 + 0.06 * intensity;
  const panAmount = 28 * intensity;
  const shakeAmount = 8 * intensity;

  switch (preset) {
    case "still_hold": {
      const scale = interpolate(frame, [0, safeDuration], [1, zoomSmall]);
      return {
        transform: `scale(${scale})`,
      };
    }

    case "slow_zoom_in": {
      const scale = interpolate(frame, [0, safeDuration], [1, zoomMedium]);
      return {
        transform: `scale(${scale})`,
      };
    }

    case "slow_zoom_out": {
      const scale = interpolate(frame, [0, safeDuration], [zoomMedium, 1]);
      return {
        transform: `scale(${scale})`,
      };
    }

    case "push_in_center": {
      const scale = interpolate(frame, [0, safeDuration], [1, 1 + 0.09 * intensity]);
      return {
        transform: `scale(${scale})`,
      };
    }

    case "pan_left": {
      const x = interpolate(frame, [0, safeDuration], [panAmount, -panAmount]);
      return {
        transform: `scale(${1 + 0.04 * intensity}) translateX(${x}px)`,
      };
    }

    case "pan_right": {
      const x = interpolate(frame, [0, safeDuration], [-panAmount, panAmount]);
      return {
        transform: `scale(${1 + 0.04 * intensity}) translateX(${x}px)`,
      };
    }

    case "pan_up": {
      const y = interpolate(frame, [0, safeDuration], [panAmount, -panAmount]);
      return {
        transform: `scale(${1 + 0.04 * intensity}) translateY(${y}px)`,
      };
    }

    case "pan_down": {
      const y = interpolate(frame, [0, safeDuration], [-panAmount, panAmount]);
      return {
        transform: `scale(${1 + 0.04 * intensity}) translateY(${y}px)`,
      };
    }

    case "handheld_tension": {
      const x = Math.sin(frame * 0.45) * shakeAmount * 0.35;
      const y = Math.cos(frame * 0.38) * shakeAmount * 0.25;
      const scale = 1 + 0.04 * intensity;
      return {
        transform: `scale(${scale}) translate(${x}px, ${y}px)`,
      };
    }

    case "impact_shake": {
      const decay = Math.max(0, 1 - progress * 4);
      const x = Math.sin(frame * 1.4) * shakeAmount * decay;
      const y = Math.cos(frame * 1.1) * shakeAmount * decay;
      const scale = 1 + 0.05 * intensity;
      return {
        transform: `scale(${scale}) translate(${x}px, ${y}px)`,
      };
    }

    default:
      return {
        transform: "scale(1.02)",
      };
  }
}
