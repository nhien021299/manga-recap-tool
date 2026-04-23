import type {
  Panel,
  RenderConfig,
  RenderMotionPreset,
  RenderPlan,
  TimelineItem,
} from "@/shared/types";

const MIN_SILENT_CLIP_MS = 1500;
const DEFAULT_FRAME_RATE = 30;

const MOTION_FAMILIES: Record<RenderMotionPreset, "push" | "drift" | "rise" | "reveal"> = {
  push_in_center: "push",
  push_in_upper_focus: "push",
  push_in_lower_focus: "push",
  drift_left_to_right: "drift",
  drift_right_to_left: "drift",
  rise_up_focus: "rise",
  pull_back_reveal: "reveal",
};

const hasNarration = (item: TimelineItem): boolean => !!item.scriptItem.voiceover_text.trim();

const hashString = (value: string): number => {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
};

const chooseMotionCandidates = (panel: Panel, durationMs: number): RenderMotionPreset[] => {
  const aspect = panel.width / Math.max(panel.height, 1);
  const isShortClip = durationMs < 2200;

  if (aspect <= 0.78) {
    return isShortClip
      ? ["push_in_center", "push_in_upper_focus", "rise_up_focus", "pull_back_reveal"]
      : ["push_in_upper_focus", "push_in_lower_focus", "rise_up_focus", "push_in_center", "pull_back_reveal"];
  }

  if (aspect >= 1.15) {
    return isShortClip
      ? ["pull_back_reveal", "push_in_center", "rise_up_focus"]
      : ["drift_left_to_right", "drift_right_to_left", "pull_back_reveal", "push_in_center"];
  }

  return isShortClip
    ? ["push_in_center", "pull_back_reveal", "rise_up_focus"]
    : ["push_in_center", "drift_left_to_right", "drift_right_to_left", "pull_back_reveal", "rise_up_focus"];
};

const selectMotionPreset = (
  panel: Panel,
  durationMs: number,
  index: number,
  previousPreset?: RenderMotionPreset
): RenderMotionPreset => {
  const candidates = chooseMotionCandidates(panel, durationMs);
  const preferredStart = hashString(`${panel.id}:${index}`) % Math.max(candidates.length, 1);
  const rotated = candidates.map((_, offset) => candidates[(preferredStart + offset) % candidates.length] as RenderMotionPreset);

  if (!previousPreset) {
    return rotated[0] ?? "push_in_center";
  }

  const previousFamily = MOTION_FAMILIES[previousPreset];
  return rotated.find((candidate) => MOTION_FAMILIES[candidate] !== previousFamily) ?? rotated[0] ?? "push_in_center";
};

const computeMotionIntensity = (item: TimelineItem, durationMs: number): number => {
  const hasAudio = item.audioStatus === "ready" && typeof item.audioDuration === "number" && item.audioDuration > 0;
  let intensity = durationMs < 2200 ? 0.62 : durationMs < 4200 ? 0.8 : 1;
  if (!hasAudio) {
    intensity -= 0.12;
  }
  return Math.max(0.5, Math.min(1, Number(intensity.toFixed(2))));
};

export const getTimelineClipDurationMs = (item: TimelineItem): number => {
  const holdAfterMs = Math.max(0, item.holdAfterMs ?? 250);
  if (item.audioStatus === "ready" && typeof item.audioDuration === "number" && item.audioDuration > 0) {
    return Math.round(item.audioDuration * 1000) + holdAfterMs;
  }
  return Math.max(MIN_SILENT_CLIP_MS, holdAfterMs);
};

export const validateRenderPlan = (timeline: TimelineItem[], panels: Panel[]): string[] => {
  if (panels.length === 0) {
    return ["No panels available for render."];
  }

  const activeItems = timeline.filter((item) => item.enabled !== false);
  if (activeItems.length === 0) {
    return ["No active clips selected for render."];
  }

  const panelIds = new Set(panels.map((panel) => panel.id));
  const errors: string[] = [];

  activeItems.forEach((item, index) => {
    if (!panelIds.has(item.panelId)) {
      errors.push(`Clip ${index + 1} is missing its source panel.`);
      return;
    }

    if (!hasNarration(item)) {
      return;
    }

    if (item.audioStatus === "stale") {
      errors.push(`Clip ${index + 1} needs regenerated audio after narration edits.`);
      return;
    }

    if (item.audioStatus === "generating") {
      errors.push(`Clip ${index + 1} audio is still generating.`);
      return;
    }

    if (
      item.audioStatus === "missing" ||
      item.audioStatus === "error" ||
      !(item.audioBlob instanceof Blob) ||
      typeof item.audioDuration !== "number" ||
      item.audioDuration <= 0
    ) {
      errors.push(`Clip ${index + 1} is missing ready audio.`);
    }
  });

  return errors;
};

export const buildRenderPlan = (
  timeline: TimelineItem[],
  panels: Panel[],
  renderConfig: RenderConfig
): RenderPlan => {
  const panelById = new Map(panels.map((panel) => [panel.id, panel]));
  const activeItems = timeline.filter((item) => item.enabled !== false);
  let startMs = 0;
  let previousPreset: RenderMotionPreset | undefined;

  const clips = activeItems.map((item, index) => {
    const panel = panelById.get(item.panelId);
    if (!panel) {
      throw new Error(`Missing panel for clip ${index + 1}.`);
    }

    const durationMs = getTimelineClipDurationMs(item);
    const motionPreset = selectMotionPreset(panel, durationMs, index, previousPreset);
    previousPreset = motionPreset;

    const clip = {
      clipId: `clip-${index + 1}-${panel.id}`,
      panelId: item.panelId,
      orderIndex: index,
      startMs,
      durationMs,
      holdAfterMs: Math.max(0, item.holdAfterMs ?? 250),
      captionText: item.scriptItem.voiceover_text.trim(),
      panelFileKey: `panel-${index + 1}`,
      audioFileKey: item.audioStatus === "ready" ? `audio-${index + 1}` : undefined,
      motionPreset,
      motionSeed: hashString(`${panel.id}:${index}:${durationMs}`),
      motionIntensity: computeMotionIntensity(item, durationMs),
      panel,
      imageBlob: item.imageBlob,
      audioBlob: item.audioStatus === "ready" ? item.audioBlob : undefined,
    };
    startMs += durationMs;
    return clip;
  });

  return {
    clips,
    totalDurationMs: startMs,
    outputWidth: renderConfig.outputWidth,
    outputHeight: Math.round(renderConfig.outputWidth / Math.max(renderConfig.aspectRatio, 0.1)),
    captionMode: renderConfig.captionMode,
    frameRate: DEFAULT_FRAME_RATE,
  };
};
