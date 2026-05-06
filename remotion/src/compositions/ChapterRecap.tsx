/**
 * ChapterRecap — Main Remotion composition.
 *
 * Takes a VideoDirectionProps input and renders a complete chapter
 * recap video with per-scene images, TTS audio, camera motions,
 * transitions, subtitles, and color grading.
 *
 * Output: 1920×1080 (16:9 horizontal YouTube)
 * Input images: 9:16 vertical manhwa scenes
 *
 * Audio architecture:
 * - Audio is rendered OUTSIDE TransitionWrapper so opacity fades
 *   don't mute narration. This fixes the "audio cut" bug.
 */

import React from "react";
import {
  AbsoluteFill,
  Sequence,
} from "remotion";
import { Scene, SceneAudio } from "../components/Scene";
import type {
  VideoDirectionProps,
  SceneDirection,
  SceneAsset,
} from "../types/direction";
import { transitionFrames } from "../effects/camera";
import { TransitionWrapper } from "../effects/transitions";

export const ChapterRecap: React.FC<VideoDirectionProps> = (props) => {
  const { scenes, assets, fps } = props;

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
        const transOutFr = transitionFrames(transOutMs, fps);

        // Previous scene transition overlap
        const prevDirection = index > 0 ? scenes[index - 1] : null;
        const transInMs = prevDirection?.transition_out?.duration_ms ?? 0;
        const transInFr = transitionFrames(transInMs, fps);

        return (
          <React.Fragment key={direction.scene}>
            {/* ── Audio layer (outside TransitionWrapper, unaffected by opacity) ── */}
            <Sequence
              from={timing.startFrame}
              durationInFrames={sceneFrames}
              name={`Audio ${direction.scene}`}
            >
              <SceneAudio direction={direction} asset={asset} />
            </Sequence>

            {/* ── Visual layer (wrapped in transitions) ── */}
            <Sequence
              from={timing.startFrame}
              durationInFrames={sceneFrames}
              name={`Scene ${direction.scene}: ${asset.title}`}
            >
              <TransitionWrapper
                transInFrames={transInFr}
                transOutFrames={transOutFr}
                totalFrames={sceneFrames}
                transInType={direction.transition_in?.type ?? "crossfade"}
                transOutType={direction.transition_out?.type ?? "crossfade"}
              >
                <Scene direction={direction} asset={asset} />
              </TransitionWrapper>
            </Sequence>
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

/* ═══════════════════════════════════════════════════════════════
   Scene Timing
   ═══════════════════════════════════════════════════════════════ */

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
