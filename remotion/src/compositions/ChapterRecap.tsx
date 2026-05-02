/**
 * ChapterRecap — Main Remotion composition.
 *
 * Takes a VideoDirectionProps input and renders a complete chapter
 * recap video with per-scene images, TTS audio, camera motions,
 * transitions, subtitles, and color grading.
 *
 * Output: 1920×1080 (16:9 horizontal YouTube)
 * Input images: 9:16 vertical manhwa scenes
 */

import React from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { Scene } from "../components/Scene";
import type {
  VideoDirectionProps,
  SceneDirection,
  SceneAsset,
} from "../types/direction";
import { transitionFrames } from "../effects/camera";

export const ChapterRecap: React.FC<VideoDirectionProps> = (props) => {
  const { scenes, assets, fps } = props;
  const frame = useCurrentFrame();

  // Build asset lookup
  const assetMap = new Map<number, SceneAsset>();
  for (const asset of assets) {
    assetMap.set(asset.scene, asset);
  }

  // Calculate scene timing with transitions
  const sceneTiming = calculateSceneTiming(scenes, fps);

  return (
    <AbsoluteFill style={{ backgroundColor: "#040810" }}>
      {sceneTiming.map((timing, index) => {
        const direction = scenes[index];
        const asset = assetMap.get(direction.scene);

        if (!asset) return null;

        const sceneFrames = Math.round(
          (direction.total_duration_ms / 1000) * fps,
        );

        // Transition overlap with next scene
        const transOutMs = direction.transition_out?.duration_ms ?? 0;
        const transOutFrames = transitionFrames(transOutMs, fps);

        // Previous scene transition overlap
        const prevDirection = index > 0 ? scenes[index - 1] : null;
        const transInMs = prevDirection?.transition_out?.duration_ms ?? 0;
        const transInFrames = transitionFrames(transInMs, fps);

        return (
          <Sequence
            key={direction.scene}
            from={timing.startFrame}
            durationInFrames={sceneFrames}
            name={`Scene ${direction.scene}: ${asset.title}`}
          >
            {/* Transition in: fade from previous */}
            <TransitionWrapper
              transInFrames={transInFrames}
              transOutFrames={transOutFrames}
              totalFrames={sceneFrames}
              transInType={direction.transition_in?.type ?? "crossfade"}
              transOutType={direction.transition_out?.type ?? "crossfade"}
            >
              <Scene direction={direction} asset={asset} />
            </TransitionWrapper>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

interface TransitionWrapperProps {
  children: React.ReactNode;
  transInFrames: number;
  transOutFrames: number;
  totalFrames: number;
  transInType: string;
  transOutType: string;
}

const TransitionWrapper: React.FC<TransitionWrapperProps> = ({
  children,
  transInFrames,
  transOutFrames,
  totalFrames,
  transInType,
  transOutType,
}) => {
  const frame = useCurrentFrame();

  let opacity = 1;

  // Fade in
  if (transInFrames > 0 && transInType !== "cut") {
    const fadeInOpacity = interpolate(frame, [0, transInFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    opacity *= fadeInOpacity;
  }

  // Fade out
  if (transOutFrames > 0 && transOutType !== "cut") {
    const fadeOutStart = totalFrames - transOutFrames;
    const fadeOutOpacity = interpolate(
      frame,
      [fadeOutStart, totalFrames],
      [1, 0],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      },
    );
    opacity *= fadeOutOpacity;
  }

  // Fade to black: add black overlay instead of changing opacity
  if (transOutType === "fade_black" || transInType === "fade_black") {
    return (
      <AbsoluteFill style={{ opacity }}>
        {children}
        <AbsoluteFill
          style={{
            backgroundColor: "#000",
            opacity: 1 - opacity,
          }}
        />
      </AbsoluteFill>
    );
  }

  // Fade to white (flash): similar but white
  if (transOutType === "fade_white" || transInType === "fade_white") {
    return (
      <AbsoluteFill style={{ opacity }}>
        {children}
        <AbsoluteFill
          style={{
            backgroundColor: "#fff",
            opacity: Math.max(0, 1 - opacity) * 0.8,
          }}
        />
      </AbsoluteFill>
    );
  }

  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

interface SceneTiming {
  startFrame: number;
  endFrame: number;
}

function calculateSceneTiming(
  scenes: SceneDirection[],
  fps: number,
): SceneTiming[] {
  const timings: SceneTiming[] = [];
  let currentFrame = 0;

  for (let i = 0; i < scenes.length; i++) {
    const sceneFrames = Math.round((scenes[i].total_duration_ms / 1000) * fps);

    timings.push({
      startFrame: currentFrame,
      endFrame: currentFrame + sceneFrames,
    });

    // Next scene starts, with transition overlap
    const transOutMs = scenes[i].transition_out?.duration_ms ?? 0;
    const overlap = transitionFrames(transOutMs, fps);
    currentFrame += sceneFrames - overlap;
  }

  return timings;
}

/**
 * Calculate the total duration in frames for the entire composition.
 */
export function calculateTotalFrames(
  scenes: SceneDirection[],
  fps: number,
): number {
  const timings = calculateSceneTiming(scenes, fps);
  if (timings.length === 0) return 1;
  return timings[timings.length - 1].endFrame;
}
