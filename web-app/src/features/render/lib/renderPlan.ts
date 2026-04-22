import type { Panel, RenderConfig, RenderPlan, TimelineItem } from "@/shared/types";

const MIN_SILENT_CLIP_MS = 1500;

const hasNarration = (item: TimelineItem): boolean =>
  !!item.scriptItem.voiceover_text.trim();

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

  const clips = activeItems.map((item, index) => {
    const panel = panelById.get(item.panelId);
    if (!panel) {
      throw new Error(`Missing panel for clip ${index + 1}.`);
    }

    const durationMs = getTimelineClipDurationMs(item);
    const clip = {
      panelId: item.panelId,
      orderIndex: index,
      startMs,
      durationMs,
      holdAfterMs: Math.max(0, item.holdAfterMs ?? 250),
      captionText: item.scriptItem.voiceover_text.trim(),
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
  };
};
