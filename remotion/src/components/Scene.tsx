/**
 * Single scene component.
 *
 * Composes the scene image, audio, and text overlays for one scene.
 */

import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
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
          colorGrade={direction.color_grade}
        />
      )}

      {/* Narration audio */}
      {asset.audioPath && (
        <Sequence from={Math.round((direction.audio_start_ms / 1000) * 30)}>
          <Audio src={staticFile(asset.audioPath)} volume={1} />
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
          <Audio src={staticFile(asset.dialogueAudioPath)} volume={0.9} />
        </Sequence>
      )}

      {/* Text overlays */}
      {direction.text_overlays.length > 0 && (
        <TextOverlayLayer overlays={direction.text_overlays} />
      )}
    </AbsoluteFill>
  );
};
