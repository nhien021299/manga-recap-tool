import { interpolate } from "remotion";
import type { TransitionPreset } from "./effectSchema";

type ResolveTransitionArgs = {
  frame: number;
  durationInFrames: number;
  transitionDurationInFrames: number;
  preset: TransitionPreset;
};

export function resolveSceneOpacity({
  frame,
  durationInFrames,
  transitionDurationInFrames,
  preset,
}: ResolveTransitionArgs) {
  const d = Math.min(transitionDurationInFrames, Math.floor(durationInFrames / 3));

  if (preset === "hard_cut") {
    return 1;
  }

  return interpolate(
    frame,
    [0, d, durationInFrames - d, durationInFrames],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );
}

export function resolveTransitionOverlay({
  frame,
  durationInFrames,
  transitionDurationInFrames,
  preset,
}: ResolveTransitionArgs): React.CSSProperties | null {
  const d = Math.min(transitionDurationInFrames, Math.floor(durationInFrames / 3));

  if (preset === "dip_to_black") {
    const opacity = interpolate(
      frame,
      [0, d, durationInFrames - d, durationInFrames],
      [1, 0, 0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    return {
      backgroundColor: "#020408",
      opacity,
      pointerEvents: "none" as const,
    };
  }

  // smooth_zoom_fade: handled by opacity + scale in the render engine
  // No additional overlay needed — the transition wrapper handles it.
  return null;
}
