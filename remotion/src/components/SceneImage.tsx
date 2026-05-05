/**
 * Scene image component with camera motion effects.
 *
 * Handles vertical (9:16) scene images composed into horizontal (16:9) frames:
 * - Blurred + darkened background fill using the SAME scene image
 * - Centered main image with camera motion (zoom/pan/Ken Burns)
 * - Cinematic vignette overlay
 * - VFX layers (film grain, particles, color effects)
 */

import React from "react";
import {
  AbsoluteFill,
  Img,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { getCameraTransform } from "../effects/camera";
import type { KeyframeEffect } from "../types/direction";
import { VfxLayer } from "../effects/vfx/VfxLayer";
import { resolveAssetPath } from "../utils/resolveAsset";

interface SceneImageProps {
  imagePath: string;
  keyframes: KeyframeEffect[];
  motionPreset: string;
  motionIntensity: number;
  colorGrade: string;
  vfxTags: string[];
}

export const SceneImage: React.FC<SceneImageProps> = ({
  imagePath,
  keyframes,
  motionPreset,
  motionIntensity,
  colorGrade,
  vfxTags,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const src = resolveAssetPath(imagePath);

  const transform = getCameraTransform(
    frame,
    durationInFrames,
    keyframes,
    motionPreset,
    motionIntensity,
  );

  // Color grade filter
  const colorFilter = getColorGradeFilter(colorGrade);

  return (
    <AbsoluteFill>
      {/* ────── Layer 1: Blurred background fill ────── */}
      {/* Uses the same scene image, scaled up + heavily blurred to fill 16:9 */}
      <AbsoluteFill>
        <Img
          src={src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: `blur(40px) brightness(0.28) saturate(1.3) ${colorFilter}`,
            transform: "scale(1.2)", // prevent blur edge gaps
          }}
        />
      </AbsoluteFill>

      {/* ────── Layer 2: Gradient overlay on background ────── */}
      {/* Adds depth and separates background from main image */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(4,6,12,0.45) 0%, rgba(4,6,12,0.25) 40%, rgba(4,6,12,0.45) 100%)",
        }}
      />

      {/* ────── Layer 3: Main centered image with camera motion ────── */}
      <AbsoluteFill
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            transform: `scale(${transform.scale}) translate(${transform.translateX}px, ${transform.translateY}px)`,
            willChange: "transform",
          }}
        >
          <Img
            src={src}
            style={{
              maxWidth: "auto",
              height: "100%",
              objectFit: "contain",
              filter: colorFilter || undefined,
            }}
          />
        </div>
      </AbsoluteFill>

      {/* ────── Layer 4: Cinematic vignette ────── */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,0.55) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* ────── Layer 5: VFX overlays ────── */}
      <VfxLayer vfxTags={vfxTags} frame={frame} durationInFrames={durationInFrames} />
    </AbsoluteFill>
  );
};

/* ═══════════════════════════════════════════════════════════════
   Color Grade Filters
   ═══════════════════════════════════════════════════════════════ */

function getColorGradeFilter(grade: string): string {
  switch (grade) {
    case "warm_firelight":
      return "sepia(0.15) saturate(1.2) brightness(1.05)";
    case "cold_blue":
      return "saturate(0.85) hue-rotate(10deg) brightness(0.95)";
    case "cold_dusk":
      return "saturate(0.8) hue-rotate(15deg) brightness(0.9)";
    case "dark_jade":
      return "saturate(0.9) hue-rotate(25deg) brightness(0.85)";
    case "blood_amber":
      return "sepia(0.25) saturate(1.3) hue-rotate(-10deg) brightness(0.9)";
    case "neutral":
    default:
      return "";
  }
}
