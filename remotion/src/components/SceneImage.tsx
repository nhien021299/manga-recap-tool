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

const DISABLED_VIDEO_DARKENING_VFX = new Set([
  "letterbox",
  "dark_smoke",
  "color_pulse",
]);

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

  const colorFilter = getColorGradeFilter(colorGrade);
  const backgroundFilter = "blur(34px) brightness(0.62) saturate(1.08)";
  const safeVfxTags = vfxTags.filter((tag) => !DISABLED_VIDEO_DARKENING_VFX.has(tag));

  return (
    <AbsoluteFill>
      {/* ────── Layer 1: Blurred background fill ────── */}
      <AbsoluteFill
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          overflow: "hidden",
          transform: "scale(1.12)",
          filter: backgroundFilter,
        }}
      >
        {[0, 1, 2].map((index) => (
          <Img
            key={index}
            src={src}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: index === 0 ? "left center" : index === 1 ? "center center" : "right center",
              transform: index === 1 ? "scaleX(-1)" : undefined,
            }}
          />
        ))}
      </AbsoluteFill>

      {/* ────── Layer 2: Gradient overlay on background ────── */}
      {/* Adds depth and separates background from main image */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(4,6,12,0.18) 0%, rgba(4,6,12,0.08) 45%, rgba(4,6,12,0.28) 100%)",
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
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: "contain",
            }}
          />
        </div>
      </AbsoluteFill>

      {/* ────── Layer 4: Cinematic vignette ────── */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 52%, rgba(0,0,0,0.28) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* ────── Layer 5: VFX overlays ────── */}
      <VfxLayer vfxTags={safeVfxTags} frame={frame} durationInFrames={durationInFrames} />
    </AbsoluteFill>
  );
};

/* ═══════════════════════════════════════════════════════════════
   Color Grade Filters (Only used for background or removed if needed)
   ═══════════════════════════════════════════════════════════════ */

function getColorGradeFilter(grade: string): string {
  // Filters removed from main image per user request
  return "";
}
