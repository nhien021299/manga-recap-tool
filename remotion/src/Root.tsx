/**
 * Root — Remotion entry point.
 *
 * Registers the ChapterRecap composition with Remotion.
 * Input props come from the orchestrator's video_direction.json.
 */

import React from "react";
import { Composition, getInputProps } from "remotion";
import { ChapterRecap, calculateTotalFrames } from "./compositions/ChapterRecap";
import type { VideoDirectionProps } from "./types/direction";

const DEFAULT_FPS = 30;
const DEFAULT_WIDTH = 1920;
const DEFAULT_HEIGHT = 1080;

export const RemotionRoot: React.FC = () => {
  const inputProps = getInputProps() as Partial<VideoDirectionProps>;

  const fps = inputProps.fps ?? DEFAULT_FPS;
  const width = inputProps.width ?? DEFAULT_WIDTH;
  const height = inputProps.height ?? DEFAULT_HEIGHT;

  // Calculate total duration from scene data
  const totalFrames =
    inputProps.scenes && inputProps.scenes.length > 0
      ? calculateTotalFrames(inputProps.scenes, fps)
      : fps * 10; // 10s default for studio preview

  return (
    <>
      <Composition
        id="ChapterRecap"
        component={ChapterRecap as unknown as React.ComponentType<Record<string, unknown>>}
        durationInFrames={totalFrames}
        fps={fps}
        width={width}
        height={height}
        defaultProps={
          {
            chapter: 0,
            total_duration_ms: 0,
            fps,
            width,
            height,
            scenes: [],
            assets: [],
            publicDir: "",
            global_settings: {},
          } satisfies VideoDirectionProps
        }
      />
    </>
  );
};
