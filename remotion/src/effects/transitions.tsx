import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";

export interface TransitionWrapperProps {
  children: React.ReactNode;
  transInFrames: number;
  transOutFrames: number;
  totalFrames: number;
  transInType: string;
  transOutType: string;
}

const isHardCut = (type: string) => type === "cut" || type === "hard_cut";
const isDipToBlack = (type: string) =>
  type === "fade_black" || type === "dip_to_black";
const isZoomFade = (type: string) =>
  type === "smooth_zoom_fade" || type === "blur_fade" || type === "flash_cut";
const isSlideSoft = (type: string) => type === "slide_soft";
const isWipeSoft = (type: string) => type === "wipe_soft";

export const TransitionWrapper: React.FC<TransitionWrapperProps> = ({
  children,
  transInFrames,
  transOutFrames,
  totalFrames,
  transInType,
  transOutType,
}) => {
  const frame = useCurrentFrame();

  let opacity = 1;

  // ── Fade in (smooth ease-out curve) ──
  if (transInFrames > 0 && !isHardCut(transInType)) {
    opacity *= interpolate(frame, [0, transInFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });
  }

  // ── Fade out (smooth ease-in curve) ──
  if (transOutFrames > 0 && !isHardCut(transOutType)) {
    const fadeOutStart = totalFrames - transOutFrames;
    opacity *= interpolate(frame, [fadeOutStart, totalFrames], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
  }

  // ── Dip to Black ──
  if (isDipToBlack(transOutType) || isDipToBlack(transInType)) {
    const blackOpacity = interpolate(opacity, [0, 1], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    return (
      <AbsoluteFill style={{ opacity }}>
        {children}
        <AbsoluteFill
          style={{
            backgroundColor: "#020408",
            opacity: blackOpacity,
            pointerEvents: "none",
          }}
        />
      </AbsoluteFill>
    );
  }

  // ── Smooth Zoom Fade ──
  if (isZoomFade(transOutType) || isZoomFade(transInType)) {
    const scaleVal = interpolate(opacity, [0, 1], [1.06, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    return (
      <AbsoluteFill
        style={{
          opacity,
          transform: `scale(${scaleVal})`,
          transformOrigin: "center center",
        }}
      >
        {children}
      </AbsoluteFill>
    );
  }

  // ── Slide Soft ──
  if (isSlideSoft(transOutType) || isSlideSoft(transInType)) {
    let slideX = 0;
    
    if (isSlideSoft(transInType) && frame < transInFrames) {
        slideX = interpolate(frame, [0, transInFrames], [20, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.cubic)
        });
    } else if (isSlideSoft(transOutType) && frame > totalFrames - transOutFrames) {
        slideX = interpolate(frame, [totalFrames - transOutFrames, totalFrames], [0, -20], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.in(Easing.cubic)
        });
    }

    return (
      <AbsoluteFill
        style={{
          opacity,
          transform: `translateX(${slideX}%)`,
          transformOrigin: "center center",
        }}
      >
        {children}
      </AbsoluteFill>
    );
  }

  // ── Wipe Soft ──
  if (isWipeSoft(transOutType) || isWipeSoft(transInType)) {
      let maskPercent = 100;
      if (isWipeSoft(transInType) && frame < transInFrames) {
          maskPercent = interpolate(frame, [0, transInFrames], [0, 100], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.inOut(Easing.quad)
          });
          return (
            <AbsoluteFill
              style={{
                opacity,
                clipPath: `inset(0 ${100 - maskPercent}% 0 0)`
              }}
            >
              {children}
            </AbsoluteFill>
          );
      } else if (isWipeSoft(transOutType) && frame > totalFrames - transOutFrames) {
          maskPercent = interpolate(frame, [totalFrames - transOutFrames, totalFrames], [100, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.inOut(Easing.quad)
          });
          return (
            <AbsoluteFill
              style={{
                opacity,
                clipPath: `inset(0 0 0 ${100 - maskPercent}%)`
              }}
            >
              {children}
            </AbsoluteFill>
          );
      }
  }

  // ── Default Crossfade ──
  const breathe = interpolate(opacity, [0, 1], [1.015, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        opacity,
        transform: `scale(${breathe})`,
        transformOrigin: "center center",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
