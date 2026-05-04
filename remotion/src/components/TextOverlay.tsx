/**
 * Text overlay component for subtitles and dialogue.
 *
 * Renders Vietnamese narration as cinematic subtitles with
 * fade-in/fade-out animations and proper text wrapping.
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
  durationInFrames: customDuration 
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
  const localDuration = endFrame - startFrame;

  // Fade animation
  const opacity = interpolate(
    localFrame,
    [0, fadeInFrames, localDuration - fadeOutFrames, localDuration],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Subtle scale-up animation (0.96 to 1)
  const scale = interpolate(
    localFrame,
    [0, 8],
    [0.96, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const style = getOverlayStyle(overlay.style, overlay.position, isPortrait, overlay.text.length);

  return (
    <div
      style={{
        ...style.container,
        opacity,
        transform: `scale(${scale})`,
      }}
    >
      <div style={style.textBox}>
        <span style={style.text}>{overlay.text}</span>
      </div>
    </div>
  );
};

interface OverlayStyles {
  container: React.CSSProperties;
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
    padding: isPortrait ? "0 40px" : "0 80px",
  };

  // Responsive config
  const config = {
    landscape: {
      bottom: "9%",
      fontSize: textLength > 42 ? 42 : 46,
      maxWidth: "68%",
      padding: "14px 28px",
    },
    portrait: {
      bottom: "9.5%",
      fontSize: textLength > 42 ? 46 : 52,
      maxWidth: "86%",
      padding: "14px 24px",
    },
  };

  const currentConfig = isPortrait ? config.portrait : config.landscape;

  const positionStyles: Record<string, React.CSSProperties> = {
    bottom_center: { bottom: currentConfig.bottom },
    top_center: { top: 60 },
    center: { top: "50%", transform: "translateY(-50%)" },
    top_left: { top: 60, justifyContent: "flex-start" },
  };

  const containerPos = positionStyles[position] ?? positionStyles.bottom_center;

  switch (styleType) {
    case "title_card":
      return {
        container: { ...baseContainer, ...containerPos },
        textBox: {
          backgroundColor: "rgba(0, 0, 0, 0.75)",
          borderRadius: 12,
          padding: "20px 40px",
          backdropFilter: "blur(8px)",
        },
        text: {
          color: "#ffffff",
          fontSize: 42,
          fontWeight: 700,
          fontFamily: "'Be Vietnam Pro', 'Roboto', 'Noto Sans', sans-serif",
          textAlign: "center",
          lineHeight: 1.4,
          textShadow: "0 2px 8px rgba(0,0,0,0.6)",
        },
      };

    case "dialogue_bubble":
      return {
        container: { ...baseContainer, ...containerPos },
        textBox: {
          backgroundColor: "rgba(20, 25, 40, 0.85)",
          borderRadius: 16,
          border: "1px solid rgba(120, 160, 220, 0.3)",
          padding: "14px 28px",
          backdropFilter: "blur(6px)",
        },
        text: {
          color: "#d0e0ff",
          fontSize: 28,
          fontWeight: 500,
          fontFamily: "'Be Vietnam Pro', 'Roboto', 'Noto Sans', sans-serif",
          fontStyle: "italic",
          textAlign: "center",
          lineHeight: 1.5,
          textShadow: "0 1px 4px rgba(0,0,0,0.4)",
        },
      };

    case "subtitle":
    default:
      return {
        container: { ...baseContainer, ...containerPos },
        textBox: {
          background: "rgba(5, 10, 18, 0.72)",
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)", // for Safari support in render
          borderRadius: 12,
          padding: currentConfig.padding,
          maxWidth: currentConfig.maxWidth,
          border: "1px solid rgba(255,255,255,0.08)",
          boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
        },
        text: {
          color: "#F4F7FB",
          fontSize: currentConfig.fontSize,
          fontWeight: 650,
          fontFamily: "'Be Vietnam Pro', 'Roboto', 'Noto Sans', sans-serif",
          textAlign: "center",
          lineHeight: 1.35,
          textShadow: "0 2px 6px rgba(0,0,0,0.85)",
          letterSpacing: "0.01em",
        },
      };
  }
}
