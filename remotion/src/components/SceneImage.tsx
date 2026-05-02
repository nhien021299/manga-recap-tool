/**
 * Scene image component with camera motion effects.
 *
 * Handles vertical (9:16) scene images composed into horizontal (16:9) frames:
 * - Blurred + darkened background fill for sides
 * - Centered main image with camera motion (zoom/pan/Ken Burns)
 * - Vignette overlay
 */

import React from "react";
import {
  AbsoluteFill,
  Img,
  useCurrentFrame,
  useVideoConfig,
  staticFile,
} from "remotion";
import { getCameraTransform } from "../effects/camera";
import type { KeyframeEffect } from "../types/direction";

interface SceneImageProps {
  imagePath: string;
  keyframes: KeyframeEffect[];
  motionPreset: string;
  colorGrade: string;
}

export const SceneImage: React.FC<SceneImageProps> = ({
  imagePath,
  keyframes,
  motionPreset,
  colorGrade,
}) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const src = staticFile(imagePath);

  const transform = getCameraTransform(
    frame,
    durationInFrames,
    keyframes,
    motionPreset,
  );

  // Color grade filter
  const colorFilter = getColorGradeFilter(colorGrade);

  return (
    <AbsoluteFill>
      {/* Blurred background fill — covers the 16:9 frame */}
      <AbsoluteFill>
        <Img
          src={src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: `blur(30px) brightness(0.3) ${colorFilter}`,
            transform: `scale(1.15)`, // prevent blur edge gaps
          }}
        />
      </AbsoluteFill>

      {/* Dark overlay on background */}
      <AbsoluteFill
        style={{
          backgroundColor: "rgba(4, 6, 12, 0.55)",
        }}
      />

      {/* Main centered image with camera motion */}
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
              borderRadius: 4,
            }}
          />
        </div>
      </AbsoluteFill>

      {/* Vignette overlay */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.5) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};

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
