import { fetchFile } from "@ffmpeg/util";
import coreURL from "@ffmpeg/core?url";
import wasmURL from "@ffmpeg/core/wasm?url";

import type { CompiledRenderClip, RenderPlan } from "@/shared/types";

const FRAME_RATE = 30;
const SILENT_AUDIO_RATE = 24000;

type FFmpegInstance = InstanceType<(typeof import("@ffmpeg/ffmpeg"))["FFmpeg"]>;

export interface RenderProgressUpdate {
  phase: string;
  progress: number;
  detail?: string;
}

let ffmpegSingleton: FFmpegInstance | null = null;
let ffmpegLoadPromise: Promise<FFmpegInstance> | null = null;
let ffmpegLogsBound = false;
const ffmpegLogHistory: string[] = [];

const pushFfmpegLog = (message: string): void => {
  ffmpegLogHistory.push(message);
  if (ffmpegLogHistory.length > 40) {
    ffmpegLogHistory.shift();
  }
};

const formatFfmpegLogs = (): string =>
  ffmpegLogHistory.length > 0 ? `\nFFmpeg logs:\n${ffmpegLogHistory.join("\n")}` : "";

const normalizeError = (error: unknown): Error => {
  if (error instanceof Error) return error;
  if (typeof error === "string") return new Error(error);
  try {
    return new Error(JSON.stringify(error));
  } catch {
    return new Error(String(error));
  }
};

const emitProgress = (
  onProgress: ((update: RenderProgressUpdate) => void) | undefined,
  phase: string,
  progress: number,
  detail?: string
): void => {
  onProgress?.({
    phase,
    progress: Math.max(0, Math.min(100, Math.round(progress))),
    detail,
  });
};

const canvasToBlob = (canvas: HTMLCanvasElement): Promise<Blob> =>
  new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
        return;
      }
      reject(new Error("Failed to encode composed frame."));
    }, "image/png");
  });

const loadImageElement = (blob: Blob): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load panel image for render."));
    };
    image.src = url;
  });

const wrapCaptionLines = (
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number
): string[] => {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let currentLine = "";

  words.forEach((word) => {
    const next = currentLine ? `${currentLine} ${word}` : word;
    if (ctx.measureText(next).width <= maxWidth) {
      currentLine = next;
      return;
    }
    if (currentLine) {
      lines.push(currentLine);
    }
    currentLine = word;
  });

  if (currentLine) {
    lines.push(currentLine);
  }

  return lines.slice(0, 4);
};

const composeFrame = async (clip: CompiledRenderClip, plan: RenderPlan): Promise<Blob> => {
  const canvas = document.createElement("canvas");
  canvas.width = plan.outputWidth;
  canvas.height = plan.outputHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Failed to create render canvas context.");
  }

  const image = await loadImageElement(clip.panel.blob);
  const width = canvas.width;
  const height = canvas.height;

  ctx.fillStyle = "#080b12";
  ctx.fillRect(0, 0, width, height);

  const imageAspect = image.width / Math.max(image.height, 1);

  let bgWidth = width;
  let bgHeight = width / Math.max(imageAspect, 0.1);
  if (bgHeight < height) {
    bgHeight = height;
    bgWidth = height * imageAspect;
  }
  const bgX = (width - bgWidth) / 2;
  const bgY = (height - bgHeight) / 2;

  ctx.save();
  ctx.filter = "blur(28px) brightness(0.32)";
  ctx.drawImage(image, bgX, bgY, bgWidth, bgHeight);
  ctx.restore();

  ctx.fillStyle = "rgba(6, 10, 18, 0.48)";
  ctx.fillRect(0, 0, width, height);

  const safeWidth = width * 0.88;
  const safeHeight = height * (plan.captionMode === "burned" && clip.captionText ? 0.68 : 0.8);
  let drawWidth = safeWidth;
  let drawHeight = safeWidth / Math.max(imageAspect, 0.1);
  if (drawHeight > safeHeight) {
    drawHeight = safeHeight;
    drawWidth = safeHeight * imageAspect;
  }

  const drawX = (width - drawWidth) / 2;
  const drawY = plan.captionMode === "burned" && clip.captionText
    ? Math.max(height * 0.1, (height - drawHeight) / 2 - height * 0.06)
    : (height - drawHeight) / 2;

  ctx.save();
  ctx.shadowColor = "rgba(0, 0, 0, 0.38)";
  ctx.shadowBlur = 32;
  ctx.drawImage(image, drawX, drawY, drawWidth, drawHeight);
  ctx.restore();

  if (plan.captionMode === "burned" && clip.captionText) {
    const paddingX = Math.round(width * 0.075);
    const maxTextWidth = width - paddingX * 2;
    ctx.font = `600 ${Math.round(width * 0.028)}px "Geist Variable", system-ui, sans-serif`;
    ctx.textBaseline = "top";
    const lines = wrapCaptionLines(ctx, clip.captionText, maxTextWidth);
    const lineHeight = Math.round(width * 0.038);
    const boxHeight = lineHeight * lines.length + 28;
    const boxY = height - boxHeight - Math.round(height * 0.06);

    ctx.fillStyle = "rgba(4, 8, 15, 0.78)";
    ctx.fillRect(paddingX - 18, boxY - 14, maxTextWidth + 36, boxHeight);

    ctx.fillStyle = "#f4f7fb";
    lines.forEach((line, index) => {
      ctx.fillText(line, paddingX, boxY + index * lineHeight);
    });
  }

  return canvasToBlob(canvas);
};

const loadFfmpeg = async (
  onProgress?: (update: RenderProgressUpdate) => void
): Promise<FFmpegInstance> => {
  if (ffmpegSingleton) {
    return ffmpegSingleton;
  }
  if (ffmpegLoadPromise) {
    return ffmpegLoadPromise;
  }

  ffmpegLoadPromise = (async () => {
    emitProgress(onProgress, "Loading FFmpeg", 5, "Fetching ffmpeg core");
    const [{ FFmpeg }] = await Promise.all([import("@ffmpeg/ffmpeg")]);
    const ffmpeg = new FFmpeg();

    if (!ffmpegLogsBound) {
      ffmpeg.on("log", ({ message }) => {
        if (message) {
          pushFfmpegLog(message);
        }
      });
      ffmpegLogsBound = true;
    }

    await ffmpeg.load({
      coreURL,
      wasmURL,
    });

    ffmpegSingleton = ffmpeg;
    emitProgress(onProgress, "Loading FFmpeg", 15, "FFmpeg ready");
    return ffmpeg;
  })();

  return ffmpegLoadPromise;
};

const assertExecSucceeded = (exitCode: number, operation: string, command: string[]): void => {
  if (exitCode === 0) return;
  throw new Error(
    `${operation} failed with ffmpeg exit code ${exitCode}.\nCommand: ${command.join(" ")}${formatFfmpegLogs()}`
  );
};

const safeDeleteFile = async (ffmpeg: FFmpegInstance, path: string | null): Promise<void> => {
  if (!path) return;
  try {
    await ffmpeg.deleteFile(path);
  } catch {
    // Ignore cleanup failures from repeated renders or partially-written files.
  }
};

const buildClipArgs = (
  clip: CompiledRenderClip,
  frameFile: string,
  audioFile: string | null,
  segmentFile: string
): string[] => {
  const clipSeconds = (clip.durationMs / 1000).toFixed(3);
  const baseArgs = [
    "-y",
    "-loop",
    "1",
    "-framerate",
    String(FRAME_RATE),
    "-i",
    frameFile,
  ];

  if (audioFile) {
    return [
      ...baseArgs,
      "-i",
      audioFile,
      "-map",
      "0:v:0",
      "-map",
      "1:a:0",
      "-t",
      clipSeconds,
      "-vf",
      `fps=${FRAME_RATE},format=yuv420p`,
      "-c:v",
      "libx264",
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-af",
      `apad=pad_dur=${(clip.holdAfterMs / 1000).toFixed(3)}`,
      segmentFile,
    ];
  }

  return [
    ...baseArgs,
    "-f",
    "lavfi",
    "-i",
    `anullsrc=channel_layout=stereo:sample_rate=${SILENT_AUDIO_RATE}`,
    "-map",
    "0:v:0",
    "-map",
    "1:a:0",
    "-t",
    clipSeconds,
    "-vf",
    `fps=${FRAME_RATE},format=yuv420p`,
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    "aac",
    segmentFile,
  ];
};

export const renderPlanToMp4 = async (
  plan: RenderPlan,
  onProgress?: (update: RenderProgressUpdate) => void
): Promise<Blob> => {
  const ffmpeg = await loadFfmpeg(onProgress);
  const sessionId = `render-${Date.now()}`;
  const segmentFiles: string[] = [];
  const tempFiles: string[] = [];

  try {
    for (let index = 0; index < plan.clips.length; index += 1) {
      const clip = plan.clips[index];
      emitProgress(
        onProgress,
        "Preparing clips",
        15 + (index / Math.max(plan.clips.length, 1)) * 55,
        `Preparing clip ${index + 1}/${plan.clips.length}`
      );

      const frameBlob = await composeFrame(clip, plan);
      const frameFile = `${sessionId}-frame-${index}.png`;
      const audioFile = clip.audioBlob ? `${sessionId}-audio-${index}.wav` : null;
      const segmentFile = `${sessionId}-segment-${index}.mp4`;
      const command = buildClipArgs(clip, frameFile, audioFile, segmentFile);

      tempFiles.push(frameFile, segmentFile);
      if (audioFile) {
        tempFiles.push(audioFile);
      }

      await ffmpeg.writeFile(frameFile, await fetchFile(frameBlob));
      if (audioFile && clip.audioBlob) {
        await ffmpeg.writeFile(audioFile, await fetchFile(clip.audioBlob));
      }

      const exitCode = await ffmpeg.exec(command);
      assertExecSucceeded(exitCode, `Clip ${index + 1} render`, command);
      segmentFiles.push(segmentFile);

      await safeDeleteFile(ffmpeg, frameFile);
      if (audioFile) {
        await safeDeleteFile(ffmpeg, audioFile);
      }
    }

    emitProgress(onProgress, "Muxing video", 78, "Concatenating segments");
    const concatFile = `${sessionId}-concat.txt`;
    const concatText = segmentFiles.map((file) => `file '${file}'`).join("\n");
    tempFiles.push(concatFile);
    await ffmpeg.writeFile(concatFile, new TextEncoder().encode(concatText));

    const outputFile = `${sessionId}-output.mp4`;
    tempFiles.push(outputFile);
    const concatCommand = [
      "-y",
      "-f",
      "concat",
      "-safe",
      "0",
      "-i",
      concatFile,
      "-c",
      "copy",
      "-movflags",
      "+faststart",
      outputFile,
    ];
    const concatExitCode = await ffmpeg.exec(concatCommand);
    assertExecSucceeded(concatExitCode, "Video mux", concatCommand);

    emitProgress(onProgress, "Finalizing export", 96, "Reading output");
    const data = await ffmpeg.readFile(outputFile);
    const outputBytes = data instanceof Uint8Array ? data : new TextEncoder().encode(String(data));
    const finalizedBytes = new Uint8Array(outputBytes);
    emitProgress(onProgress, "Done", 100, "MP4 ready");
    return new Blob([finalizedBytes], { type: "video/mp4" });
  } catch (error) {
    throw normalizeError(error);
  } finally {
    for (const file of tempFiles) {
      await safeDeleteFile(ffmpeg, file);
    }
  }
};
