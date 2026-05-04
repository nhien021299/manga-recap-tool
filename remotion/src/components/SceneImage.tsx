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
  const src = imagePath;

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
   VFX Layer — Code-only visual effects (CSS + animated)
   ═══════════════════════════════════════════════════════════════ */

interface VfxLayerProps {
  vfxTags: string[];
  frame: number;
  durationInFrames: number;
}

const VfxLayer: React.FC<VfxLayerProps> = ({ vfxTags, frame, durationInFrames }) => {
  if (vfxTags.length === 0) return null;

  const progress = durationInFrames > 1 ? frame / (durationInFrames - 1) : 1;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* ── Film Grain ── */}
      {vfxTags.includes("film_grain") && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0.06,
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
            backgroundSize: "128px 128px",
            // Animate grain by shifting the background position each frame
            backgroundPosition: `${(frame * 73) % 128}px ${(frame * 47) % 128}px`,
            mixBlendMode: "overlay",
          }}
        />
      )}

      {/* ── Cinematic Letterbox ── */}
      {vfxTags.includes("letterbox") && (
        <>
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: "6%",
              background: "#000",
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: "6%",
              background: "#000",
            }}
          />
        </>
      )}

      {/* ── Rain ── */}
      {vfxTags.includes("rain") && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0.35,
            background: `repeating-linear-gradient(
              ${100 + Math.sin(progress * Math.PI * 0.5) * 5}deg,
              transparent,
              transparent 18px,
              rgba(174,194,224,0.18) 18px,
              rgba(174,194,224,0.18) 19px
            )`,
            // Rain falls by shifting background
            backgroundPosition: `0px ${frame * 12}px`,
            mixBlendMode: "screen",
          }}
        />
      )}

      {/* ── Dust Particles ── */}
      {vfxTags.includes("dust") && (
        <div style={{ position: "absolute", inset: 0 }}>
          {Array.from({ length: 8 }).map((_, i) => {
            const x = ((i * 137 + frame * (0.3 + i * 0.08)) % 110) - 5;
            const y = ((i * 97 + frame * (0.15 + i * 0.05)) % 110) - 5;
            const size = 2 + (i % 3);
            const op = 0.15 + (i % 4) * 0.06;
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: `${x}%`,
                  top: `${y}%`,
                  width: size,
                  height: size,
                  borderRadius: "50%",
                  background: `rgba(255,240,200,${op})`,
                  filter: `blur(${1 + (i % 2)}px)`,
                }}
              />
            );
          })}
        </div>
      )}

      {/* ── Fire Embers ── */}
      {vfxTags.includes("fire_embers") && (
        <div style={{ position: "absolute", inset: 0 }}>
          {/* Warm bottom glow */}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: "25%",
              background:
                "linear-gradient(to top, rgba(255,80,0,0.12), transparent)",
              filter: "blur(20px)",
            }}
          />
          {/* Floating embers */}
          {Array.from({ length: 6 }).map((_, i) => {
            const x = ((i * 157 + frame * (0.4 + i * 0.1)) % 100);
            const y = 100 - ((i * 83 + frame * (0.6 + i * 0.15)) % 100);
            const size = 2 + (i % 3);
            const hue = 20 + (i % 4) * 10; // orange to red
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: `${x}%`,
                  top: `${y}%`,
                  width: size,
                  height: size,
                  borderRadius: "50%",
                  background: `hsl(${hue}, 100%, 55%)`,
                  boxShadow: `0 0 ${size * 2}px hsl(${hue}, 100%, 45%)`,
                  opacity: 0.5 + Math.sin(frame * 0.3 + i) * 0.3,
                  filter: "blur(0.5px)",
                }}
              />
            );
          })}
        </div>
      )}

      {/* ── Cold Mist ── */}
      {vfxTags.includes("cold_mist") && (
        <>
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: "35%",
              background:
                "linear-gradient(to top, rgba(180,200,230,0.12) 0%, transparent 100%)",
              filter: "blur(30px)",
              transform: `translateX(${Math.sin(progress * Math.PI * 2) * 20}px)`,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: "20%",
              background:
                "linear-gradient(to top, rgba(200,210,240,0.08) 0%, transparent 100%)",
              filter: "blur(40px)",
              transform: `translateX(${Math.cos(progress * Math.PI * 2) * 30}px)`,
            }}
          />
        </>
      )}

      {/* ── Dark Smoke ── */}
      {vfxTags.includes("dark_smoke") && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse at 50% 80%, rgba(0,0,0,0.35) 0%, transparent 55%)",
            filter: "blur(25px)",
            transform: `translateY(${Math.sin(progress * Math.PI) * -10}px)`,
          }}
        />
      )}

      {/* ── Blood Spatter ── */}
      {vfxTags.includes("blood_spatter") && (
        <>
          <div
            style={{
              position: "absolute",
              top: "8%",
              left: "8%",
              width: "22%",
              height: "22%",
              background:
                "radial-gradient(circle, rgba(120,0,0,0.5) 0%, transparent 65%)",
              filter: "blur(6px)",
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "12%",
              right: "18%",
              width: "16%",
              height: "16%",
              background:
                "radial-gradient(circle, rgba(120,0,0,0.35) 0%, transparent 65%)",
              filter: "blur(8px)",
            }}
          />
        </>
      )}

      {/* ── Speed Lines ── */}
      {vfxTags.includes("speed_lines") && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0.2,
            background: `repeating-linear-gradient(
              ${85 + Math.sin(frame * 0.2) * 3}deg,
              transparent,
              transparent 8px,
              rgba(255,255,255,0.08) 8px,
              rgba(255,255,255,0.08) 9px
            )`,
            backgroundPosition: `0px ${frame * 8}px`,
          }}
        />
      )}

      {/* ── Edge Glow (dramatic light bloom) ── */}
      {vfxTags.includes("edge_glow") && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse at 50% 30%, rgba(255,200,100,0.08) 0%, transparent 60%)",
            opacity: 0.6 + Math.sin(progress * Math.PI * 2) * 0.3,
          }}
        />
      )}

      {/* ── Color Pulse (subtle intensity beat) ── */}
      {vfxTags.includes("color_pulse") && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(180,0,30,0.04)",
            opacity: 0.4 + Math.sin(frame * 0.15) * 0.4,
            mixBlendMode: "color",
          }}
        />
      )}
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
