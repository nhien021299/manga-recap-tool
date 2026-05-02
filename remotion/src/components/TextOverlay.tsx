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
}

export const TextOverlayLayer: React.FC<TextOverlayProps> = ({ overlays }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

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
  const startFrame = Math.floor(overlay.start_pct * durationInFrames);
  const endFrame = Math.floor(overlay.end_pct * durationInFrames);
  const fadeInFrames = 8;
  const fadeOutFrames = 8;

  if (frame < startFrame || frame > endFrame) return null;

  const opacity = interpolate(
    frame,
    [
      startFrame,
      startFrame + fadeInFrames,
      endFrame - fadeOutFrames,
      endFrame,
    ],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const style = getOverlayStyle(overlay.style, overlay.position);

  return (
    <div
      style={{
        ...style.container,
        opacity,
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
): OverlayStyles {
  const baseContainer: React.CSSProperties = {
    position: "absolute",
    left: 0,
    right: 0,
    display: "flex",
    justifyContent: "center",
    padding: "0 80px",
  };

  const positionStyles: Record<string, React.CSSProperties> = {
    bottom_center: { bottom: 60 },
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
          fontFamily:
            "'Be Vietnam Pro', 'Roboto', 'Noto Sans', sans-serif",
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
          fontFamily:
            "'Be Vietnam Pro', 'Roboto', 'Noto Sans', sans-serif",
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
          backgroundColor: "rgba(4, 8, 16, 0.82)",
          borderRadius: 10,
          padding: "12px 24px",
          maxWidth: 1400,
          backdropFilter: "blur(4px)",
        },
        text: {
          color: "#f0f4fa",
          fontSize: 30,
          fontWeight: 500,
          fontFamily:
            "'Be Vietnam Pro', 'Roboto', 'Noto Sans', sans-serif",
          textAlign: "center",
          lineHeight: 1.55,
          textShadow: "0 1px 4px rgba(0,0,0,0.5)",
          letterSpacing: "0.02em",
        },
      };
  }
}
