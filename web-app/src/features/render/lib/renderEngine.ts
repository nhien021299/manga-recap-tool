import { fetchFile } from "@ffmpeg/util";
import coreURL from "@ffmpeg/core?url";
import wasmURL from "@ffmpeg/core/wasm?url";

import type { CompiledRenderClip, RenderPlan } from "@/shared/types";

const SILENT_AUDIO_RATE = 24000;

type FFmpegInstance = InstanceType<(typeof import("@ffmpeg/ffmpeg"))["FFmpeg"]>;

export interface RenderProgressUpdate {
  phase: string;
  progress: number;
  detail?: string;
}

interface MotionTransform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

let ffmpegSingleton: FFmpegInstance | null = null;
let ffmpegLoadPromise: Promise<FFmpegInstance> | null = null;
let ffmpegLogsBound = false;
const ffmpegLogHistory: string[] = [];

const resetFfmpegState = (): void => {
  ffmpegSingleton = null;
  ffmpegLoadPromise = null;
  ffmpegLogsBound = false;
};

export const cancelBrowserRenderSession = (): void => {
  if (ffmpegSingleton) {
    ffmpegSingleton.terminate();
  }
  resetFfmpegState();
};

const pushFfmpegLog = (message: string): void => {
  ffmpegLogHistory.push(message);
  if (ffmpegLogHistory.length > 60) {
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

const isAbortError = (error: unknown): boolean =>
  error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error
      ? /abort|terminated/i.test(error.message)
      : typeof error === "string"
        ? /abort|terminated/i.test(error)
        : false;

const throwIfAborted = (signal?: AbortSignal): void => {
  if (signal?.aborted) {
    throw new DOMException("Browser render cancelled by user.", "AbortError");
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

const easeInOut = (progress: number): number => 0.5 - Math.cos(Math.PI * progress) / 2;

const getMotionTransform = (
  clip: CompiledRenderClip,
  progress: number,
  drawWidth: number,
  drawHeight: number
): MotionTransform => {
  const eased = easeInOut(progress);
  const intensity = clip.motionIntensity;
  const panX = drawWidth * (0.04 + intensity * 0.03);
  const panY = drawHeight * (0.03 + intensity * 0.025);

  switch (clip.motionPreset) {
    case "push_in_upper_focus":
      return {
        scale: 1.04 + intensity * 0.09 * eased,
        offsetX: 0,
        offsetY: panY * eased,
      };
    case "push_in_lower_focus":
      return {
        scale: 1.04 + intensity * 0.09 * eased,
        offsetX: 0,
        offsetY: -panY * eased,
      };
    case "drift_left_to_right":
      return {
        scale: 1.05 + intensity * 0.05 * eased,
        offsetX: panX * (eased * 2 - 1),
        offsetY: 0,
      };
    case "drift_right_to_left":
      return {
        scale: 1.05 + intensity * 0.05 * eased,
        offsetX: -panX * (eased * 2 - 1),
        offsetY: 0,
      };
    case "rise_up_focus":
      return {
        scale: 1.04 + intensity * 0.07 * eased,
        offsetX: 0,
        offsetY: panY * (0.4 - eased),
      };
    case "pull_back_reveal":
      return {
        scale: 1.12 - intensity * 0.08 * eased,
        offsetX: 0,
        offsetY: -panY * 0.25 * eased,
      };
    case "push_in_center":
    default:
      return {
        scale: 1.04 + intensity * 0.08 * eased,
        offsetX: 0,
        offsetY: 0,
      };
  }
};

const drawVignette = (ctx: CanvasRenderingContext2D, width: number, height: number): void => {
  const gradient = ctx.createRadialGradient(width / 2, height / 2, width * 0.22, width / 2, height / 2, width * 0.72);
  gradient.addColorStop(0, "rgba(0, 0, 0, 0)");
  gradient.addColorStop(1, "rgba(0, 0, 0, 0.22)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
};

const composeFrame = async (
  clip: CompiledRenderClip,
  plan: RenderPlan,
  image: HTMLImageElement,
  progress: number
): Promise<Blob> => {
  const canvas = document.createElement("canvas");
  canvas.width = plan.outputWidth;
  canvas.height = plan.outputHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Failed to create render canvas context.");
  }

  const width = canvas.width;
  const height = canvas.height;
  const imageAspect = image.width / Math.max(image.height, 1);

  ctx.fillStyle = "#080b12";
  ctx.fillRect(0, 0, width, height);

  let bgWidth = width;
  let bgHeight = width / Math.max(imageAspect, 0.1);
  if (bgHeight < height) {
    bgHeight = height;
    bgWidth = height * imageAspect;
  }
  const bgX = (width - bgWidth) / 2;
  const bgY = (height - bgHeight) / 2;
  const bgTransform = getMotionTransform(clip, Math.min(1, progress * 0.85), bgWidth, bgHeight);

  ctx.save();
  ctx.filter = "blur(28px) brightness(0.32)";
  ctx.translate(width / 2, height / 2);
  ctx.scale(Math.max(1, bgTransform.scale * 1.01), Math.max(1, bgTransform.scale * 1.01));
  ctx.translate(-width / 2 + bgTransform.offsetX * 0.3, -height / 2 + bgTransform.offsetY * 0.3);
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

  const baseDrawX = (width - drawWidth) / 2;
  const baseDrawY =
    plan.captionMode === "burned" && clip.captionText
      ? Math.max(height * 0.1, (height - drawHeight) / 2 - height * 0.06)
      : (height - drawHeight) / 2;

  const transform = getMotionTransform(clip, progress, drawWidth, drawHeight);
  const animatedWidth = drawWidth * transform.scale;
  const animatedHeight = drawHeight * transform.scale;
  const drawX = baseDrawX - (animatedWidth - drawWidth) / 2 + transform.offsetX;
  const drawY = baseDrawY - (animatedHeight - drawHeight) / 2 + transform.offsetY;

  ctx.save();
  ctx.shadowColor = "rgba(0, 0, 0, 0.38)";
  ctx.shadowBlur = 32;
  ctx.drawImage(image, drawX, drawY, animatedWidth, animatedHeight);
  ctx.restore();

  drawVignette(ctx, width, height);

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
    ctx.beginPath();
    ctx.roundRect(paddingX - 18, boxY - 14, maxTextWidth + 36, boxHeight, 24);
    ctx.fill();

    ctx.fillStyle = "#f4f7fb";
    lines.forEach((line, index) => {
      ctx.fillText(line, paddingX, boxY + index * lineHeight);
    });
  }

  return canvasToBlob(canvas);
};

const loadFfmpeg = async (
  onProgress?: (update: RenderProgressUpdate) => void,
  signal?: AbortSignal
): Promise<FFmpegInstance> => {
  throwIfAborted(signal);
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

    await ffmpeg.load(
      {
        coreURL,
        wasmURL,
      },
      { signal }
    );

    ffmpegSingleton = ffmpeg;
    emitProgress(onProgress, "Loading FFmpeg", 12, "FFmpeg ready");
    return ffmpeg;
  })().catch((error) => {
    resetFfmpegState();
    throw error;
  });

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

const writeClipFrames = async (
  ffmpeg: FFmpegInstance,
  clip: CompiledRenderClip,
  plan: RenderPlan,
  image: HTMLImageElement,
  sessionId: string,
  clipIndex: number,
  onProgress?: (update: RenderProgressUpdate) => void,
  signal?: AbortSignal
): Promise<string[]> => {
  const totalFrames = Math.max(1, Math.round((clip.durationMs / 1000) * plan.frameRate));
  const framePaths: string[] = [];
  const baseProgress = 15 + ((clipIndex - 1) / Math.max(plan.clips.length, 1)) * 52;
  const clipProgressSpan = 52 / Math.max(plan.clips.length, 1);

  for (let frameIndex = 0; frameIndex < totalFrames; frameIndex += 1) {
    throwIfAborted(signal);
    const progress = totalFrames === 1 ? 1 : frameIndex / (totalFrames - 1);
    const frameBlob = await composeFrame(clip, plan, image, progress);
    const framePath = `${sessionId}-clip-${clipIndex}-frame-${String(frameIndex + 1).padStart(5, "0")}.png`;
    framePaths.push(framePath);
    await ffmpeg.writeFile(framePath, await fetchFile(frameBlob), { signal });

    if (frameIndex === totalFrames - 1 || frameIndex % Math.max(1, Math.round(plan.frameRate / 2)) === 0) {
      emitProgress(
        onProgress,
        "Browser fallback render",
        baseProgress + (frameIndex / Math.max(totalFrames, 1)) * clipProgressSpan * 0.72,
        `Animating clip ${clipIndex}/${plan.clips.length}`
      );
    }
  }

  return framePaths;
};

const buildClipArgs = (
  clip: CompiledRenderClip,
  plan: RenderPlan,
  framePattern: string,
  audioFile: string | null,
  segmentFile: string
): string[] => {
  const clipSeconds = (clip.durationMs / 1000).toFixed(3);
  const baseArgs = ["-y", "-framerate", String(plan.frameRate), "-i", framePattern];

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
      `fps=${plan.frameRate},format=yuv420p`,
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
    `fps=${plan.frameRate},format=yuv420p`,
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
  onProgress?: (update: RenderProgressUpdate) => void,
  signal?: AbortSignal
): Promise<Blob> => {
  const ffmpeg = await loadFfmpeg(onProgress, signal);
  const sessionId = `render-${Date.now()}`;
  const segmentFiles: string[] = [];
  const tempFiles: string[] = [];
  const handleAbort = () => {
    cancelBrowserRenderSession();
  };

  signal?.addEventListener("abort", handleAbort, { once: true });

  try {
    for (let index = 0; index < plan.clips.length; index += 1) {
      throwIfAborted(signal);
      const clip = plan.clips[index]!;
      const clipNumber = index + 1;
      const image = await loadImageElement(clip.panel.blob);
      const framePaths = await writeClipFrames(ffmpeg, clip, plan, image, sessionId, clipNumber, onProgress, signal);
      tempFiles.push(...framePaths);

      const framePattern = `${sessionId}-clip-${clipNumber}-frame-%05d.png`;
      const audioFile = clip.audioBlob ? `${sessionId}-audio-${clipNumber}.wav` : null;
      const segmentFile = `${sessionId}-segment-${clipNumber}.mp4`;
      const command = buildClipArgs(clip, plan, framePattern, audioFile, segmentFile);

      tempFiles.push(segmentFile);
      if (audioFile) {
        tempFiles.push(audioFile);
        await ffmpeg.writeFile(audioFile, await fetchFile(clip.audioBlob!), { signal });
      }

      emitProgress(
        onProgress,
        "Browser fallback render",
        15 + (clipNumber / Math.max(plan.clips.length, 1)) * 52,
        `Encoding clip ${clipNumber}/${plan.clips.length}`
      );
      const exitCode = await ffmpeg.exec(command, -1, { signal });
      assertExecSucceeded(exitCode, `Clip ${clipNumber} encode`, command);
      segmentFiles.push(segmentFile);

      for (const framePath of framePaths) {
        await safeDeleteFile(ffmpeg, framePath);
      }
      if (audioFile) {
        await safeDeleteFile(ffmpeg, audioFile);
      }
    }

    emitProgress(onProgress, "Browser fallback render", 80, "Concatenating final MP4");
    const concatFile = `${sessionId}-concat.txt`;
    const concatText = segmentFiles.map((file) => `file '${file}'`).join("\n");
    tempFiles.push(concatFile);
    await ffmpeg.writeFile(concatFile, new TextEncoder().encode(concatText), { signal });

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
    const concatExitCode = await ffmpeg.exec(concatCommand, -1, { signal });
    assertExecSucceeded(concatExitCode, "Final concat", concatCommand);

    emitProgress(onProgress, "Browser fallback render", 96, "Reading rendered MP4");
    const data = await ffmpeg.readFile(outputFile, "binary", { signal });
    const outputBytes = data instanceof Uint8Array ? data : new TextEncoder().encode(String(data));
    const finalizedBytes = new Uint8Array(outputBytes);
    emitProgress(onProgress, "Browser fallback render", 100, "Cinematic fallback MP4 ready");
    return new Blob([finalizedBytes], { type: "video/mp4" });
  } catch (error) {
    if (isAbortError(error) || signal?.aborted) {
      throw new DOMException("Browser render cancelled by user.", "AbortError");
    }
    throw normalizeError(error);
  } finally {
    signal?.removeEventListener("abort", handleAbort);
    for (const file of tempFiles) {
      await safeDeleteFile(ffmpeg, file);
    }
  }
};
