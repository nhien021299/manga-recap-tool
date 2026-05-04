/**
 * Single scene component.
 *
 * Composes the scene image, audio, and text overlays for one scene.
 *
 * IMPORTANT: Audio is rendered OUTSIDE the visual transition wrapper
 * so that opacity fades don't mute the audio. The parent ChapterRecap
 * wraps only the visual content in TransitionWrapper.
 */

import React from "react";
import { AbsoluteFill, Audio, Sequence } from "remotion";
import { SceneImage } from "./SceneImage";
import { TextOverlayLayer } from "./TextOverlay";
import type { SceneDirection, SceneAsset } from "../types/direction";

interface SceneProps {
  direction: SceneDirection;
  asset: SceneAsset;
}

export const Scene: React.FC<SceneProps> = ({ direction, asset }) => {
  return (
    <AbsoluteFill>
      {/* Scene image with camera motion and color grading */}
      {asset.imagePath && (
        <SceneImage
          imagePath={asset.imagePath}
          keyframes={direction.keyframes}
          motionPreset={direction.motion_preset}
          motionIntensity={direction.motion_intensity ?? 1.0}
          colorGrade={direction.color_grade}
          vfxTags={direction.vfx_tags ?? []}
        />
      )}

      {/* Text overlays synced with audio */}
      {direction.text_overlays.length > 0 && (
        <Sequence
          from={Math.round((direction.audio_start_ms / 1000) * 30)}
          durationInFrames={Math.round((asset.audioDurationMs / 1000) * 30)}
        >
          <TextOverlayLayer
            overlays={direction.text_overlays}
            durationInFrames={Math.round((asset.audioDurationMs / 1000) * 30)}
          />
        </Sequence>
      )}
    </AbsoluteFill>
  );
};

/**
 * Audio layer for a scene — rendered separately from visuals
 * so that transition opacity doesn't mute audio.
 */
export const SceneAudio: React.FC<SceneProps> = ({ direction, asset }) => {
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Narration audio */}
      {asset.audioPath && (
        <Sequence from={Math.round((direction.audio_start_ms / 1000) * 30)}>
          <Audio src={asset.audioPath} volume={1} />
        </Sequence>
      )}

      {/* Dialogue audio (plays after narration) */}
      {asset.dialogueAudioPath && asset.audioDurationMs > 0 && (
        <Sequence
          from={Math.round(
            ((direction.audio_start_ms + asset.audioDurationMs + 300) / 1000) *
              30,
          )}
        >
          <Audio src={asset.dialogueAudioPath} volume={0.9} />
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
