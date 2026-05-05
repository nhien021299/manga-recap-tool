/**
 * Text overlay component for subtitles and dialogue.
 *
 * Renders Vietnamese narration as cinematic subtitles with
 * fade-in/fade-out animations and proper text wrapping.
 *
 * Style direction:
 * - Default subtitle: dark manhwa cinematic glass box.
 * - Optional subtitle_stroke: no background, comic-style stroke for testing.
 */

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { TextOverlay as TextOverlayType } from "../types/direction";

interface TextOverlayProps {
  overlays: TextOverlayType[];
  durationInFrames?: number;
}

export const TextOverlayLayer: React.FC<TextOverlayProps> = ({
  overlays,
  durationInFrames: customDuration,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames: compositionDuration } = useVideoConfig();
  const durationInFrames = customDuration ?? compositionDuration;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {overlays.map((overlay, index) => (
        <SingleOverlay
          key={index}
          overlay={overlay}
          frame={frame}
          durationInFrames={durationInFrames}
        />
      ))}
    </AbsoluteFill>
  );
};

interface SingleOverlayProps {
  overlay: TextOverlayType;
  frame: number;
  durationInFrames: number;
}

const SingleOverlay: React.FC<SingleOverlayProps> = ({
  overlay,
  frame,
  durationInFrames,
}) => {
  const { width, height } = useVideoConfig();
  const isPortrait = height > width;

  const startFrame = Math.floor(overlay.start_pct * durationInFrames);
  const endFrame = Math.floor(overlay.end_pct * durationInFrames);
  const fadeInFrames = 6;
  const fadeOutFrames = 6;

  if (frame < startFrame || frame > endFrame) return null;

  const localFrame = frame - startFrame;
  const localDuration = Math.max(endFrame - startFrame, 1);

  const opacity = interpolate(
    localFrame,
    [0, fadeInFrames, localDuration - fadeOutFrames, localDuration],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const scale = interpolate(localFrame, [0, 8], [0.96, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const style = getOverlayStyle(
    overlay.style,
    overlay.position,
    isPortrait,
    overlay.text.length
  );

  return (
    <div
      style={{
        ...style.container,
        opacity,
      }}
    >
      <div
        style={{
          ...style.motionWrapper,
          transform: `scale(${scale})`,
        }}
      >
        <div style={style.textBox}>
          <span style={style.text}>{overlay.text.toUpperCase()}</span>
        </div>
      </div>
    </div>
  );
};

interface OverlayStyles {
  container: React.CSSProperties;
  motionWrapper: React.CSSProperties;
  textBox: React.CSSProperties;
  text: React.CSSProperties;
}

function getOverlayStyle(
  styleType: string,
  position: string,
  isPortrait: boolean,
  textLength: number
): OverlayStyles {
  const baseContainer: React.CSSProperties = {
    position: "absolute",
    left: 0,
    right: 0,
    display: "flex",
    justifyContent: "center",
    padding: isPortrait ? "0 34px" : "0 72px",
    zIndex: 20,
  };

  const baseMotionWrapper: React.CSSProperties = {
    display: "flex",
    justifyContent: "center",
    width: "100%",
    transformOrigin: "center center",
  };

  /**
   * Default subtitle config for dark manhwa recap.
   */
  const config = {
    landscape: {
      bottom: "8.5%",
      fontSize: 42,
      fontWeight: 700,
      lineHeight: 1.26,
      maxWidth: "62%",
      padding: "11px 22px",
      strokeWidth: 0.4,
    },
    portrait: {
      bottom: "8.5%",
      fontSize: 46,
      fontWeight: 700,
      lineHeight: 1.26,
      maxWidth: "82%",
      padding: "11px 19px",
      strokeWidth: 0.45,
    },
  };

  const currentConfig = isPortrait ? config.portrait : config.landscape;

  const positionStyles: Record<string, React.CSSProperties> = {
    bottom_center: { bottom: currentConfig.bottom },
    top_center: { top: isPortrait ? 72 : 60 },
    center: { top: "50%", transform: "translateY(-50%)" },
    top_left: {
      top: isPortrait ? 72 : 60,
      justifyContent: "flex-start",
    },
  };

  const containerPos = positionStyles[position] ?? positionStyles.bottom_center;

  const commonFont: React.CSSProperties = {
    fontFamily:
      "'Be Vietnam Pro', 'Roboto Condensed', 'Arial', 'Noto Sans', sans-serif",
    fontVariantLigatures: "none",
    WebkitFontSmoothing: "antialiased",
    MozOsxFontSmoothing: "grayscale",
  };

  switch (styleType) {
    case "title_card":
      return {
        container: { ...baseContainer, ...containerPos },
        motionWrapper: baseMotionWrapper,
        textBox: {
          background: "rgba(5, 10, 18, 0.76)",
          borderRadius: 12,
          padding: isPortrait ? "16px 28px" : "18px 34px",
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
          border: "1px solid rgba(255,255,255,0.07)",
          boxShadow: "0 10px 30px rgba(0,0,0,0.36)",
          textAlign: "center",
          maxWidth: isPortrait ? "86%" : "66%",
        },
        text: {
          ...commonFont,
          color: "#F4F7FB",
          fontSize: isPortrait ? 44 : 40,
          fontWeight: 750,
          lineHeight: 1.28,
          textShadow: "0 2px 8px rgba(0,0,0,0.75)",
        },
      };

    case "dialogue_bubble":
      return {
        container: { ...baseContainer, ...containerPos },
        motionWrapper: baseMotionWrapper,
        textBox: {
          background: "rgba(240, 244, 255, 0.95)",
          borderRadius: "20px 20px 20px 4px",
          border: "2px solid rgba(0, 0, 0, 0.8)",
          padding: isPortrait ? "14px 22px" : "16px 26px",
          boxShadow: "4px 4px 0px rgba(0,0,0,0.4)",
          textAlign: "center",
          maxWidth: isPortrait ? "75%" : "55%",
        },
        text: {
          ...commonFont,
          color: "#050A12",
          fontSize: isPortrait ? 38 : 34,
          fontWeight: 800,
          fontStyle: "italic",
          lineHeight: 1.36,
        },
      };

    /**
     * Optional style for A/B testing:
     * - Similar to common YouTube cartoon recap subtitles.
     * - No background box.
     * - Stronger stroke.
     *
     * Now the PRIMARY style for all subtitles in manhwa recaps.
     * Matches YouTube recap channel aesthetic: bold, clean, no-box.
     */
    case "subtitle_stroke":
      return {
        container: { ...baseContainer, ...containerPos },
        motionWrapper: baseMotionWrapper,
        textBox: {
          maxWidth: isPortrait ? "86%" : "72%",
          padding: "0 8px",
          textAlign: "center",
        },
        text: {
          ...commonFont,
          color: "#FFFFFF",
          fontSize: isPortrait ? 50 : 46,
          fontWeight: 900,
          lineHeight: 1.22,
          WebkitTextStroke: isPortrait
            ? "3.5px rgba(0,0,0,0.95)"
            : "3px rgba(0,0,0,0.95)",
          paintOrder: "stroke fill",
          textShadow:
            "0 2px 0 rgba(0,0,0,0.85), 0 4px 0 rgba(0,0,0,0.6), 0 6px 14px rgba(0,0,0,0.5)",
          letterSpacing: "-0.3px",
        },
      };

    case "subtitle":
    default:
      return {
        container: { ...baseContainer, ...containerPos },
        motionWrapper: baseMotionWrapper,
        textBox: {
          background: "rgba(5, 10, 18, 0.62)",
          backdropFilter: "blur(5px)",
          WebkitBackdropFilter: "blur(5px)",
          borderRadius: 10,
          padding: currentConfig.padding,
          maxWidth: currentConfig.maxWidth,
          border: "1px solid rgba(255,255,255,0.045)",
          boxShadow: "0 8px 22px rgba(0,0,0,0.28)",
          textAlign: "center",
        },
        text: {
          ...commonFont,
          color: "#F4F7FB",
          fontSize: currentConfig.fontSize,
          fontWeight: currentConfig.fontWeight,
          lineHeight: currentConfig.lineHeight,
          textShadow:
            "0 1px 1px rgba(0,0,0,0.8), 0 2px 7px rgba(0,0,0,0.9)",
          WebkitTextStroke: `${currentConfig.strokeWidth}px rgba(0,0,0,0.55)`,
          paintOrder: "stroke fill",
          letterSpacing: "-0.1px",
        },
      };
  }
}
