import type {
  Panel,
  RenderConfig,
  RenderMotionPreset,
  RenderTransitionPreset,
  RenderPlan,
  TimelineItem,
  CompiledRenderClip,
} from "@/shared/types";
import { resolveSceneEffects } from "./effectResolver";
import type { SceneType, SceneMood, MotionPreset, TransitionPreset } from "./effectSchema";

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
  // New presets
  still_hold: "push",
  slow_zoom_in: "push",
  slow_zoom_out: "reveal",
  pan_left: "drift",
  pan_right: "drift",
  pan_up: "rise",
  pan_down: "rise",
  handheld_tension: "drift",
  impact_shake: "push",
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
  // Boosted: was 0.62/0.8/1 — too subtle for cinematic recaps
  let intensity = durationMs < 2200 ? 0.7 : durationMs < 4200 ? 0.85 : 1;
  if (!hasAudio) {
    intensity -= 0.1;
  }
  return Math.max(0.55, Math.min(1, Number(intensity.toFixed(2))));
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

    // Determine motion and transition using preset resolver or legacy auto-selection
    const hasEffectMetadata = !!(item.sceneType || item.mood || item.motionPreset || item.transition);
    let motionPreset: RenderMotionPreset;
    let motionIntensity: number;
    let transition: RenderTransitionPreset;
    let transitionDurationMs: number;

    if (hasEffectMetadata) {
      // Use preset-driven resolver: validates, clamps, applies mood modifiers
      const resolved = resolveSceneEffects({
        sceneType: item.sceneType as SceneType | undefined,
        mood: item.mood as SceneMood | undefined,
        motionPreset: item.motionPreset as MotionPreset | undefined,
        motionIntensity: item.motionIntensity,
        transition: item.transition as TransitionPreset | undefined,
        transitionDurationMs: item.transitionDurationMs,
      });
      motionPreset = resolved.motionPreset as RenderMotionPreset;
      motionIntensity = resolved.motionIntensity;
      transition = resolved.transition as RenderTransitionPreset;
      transitionDurationMs = resolved.transitionDurationMs;
    } else {
      // Fallback to legacy auto-selection based on panel aspect/duration
      motionPreset = selectMotionPreset(panel, durationMs, index, previousPreset);
      motionIntensity = computeMotionIntensity(item, durationMs);
      transition = "crossfade";
      transitionDurationMs = 500;
    }

    previousPreset = motionPreset;

    const text_overlays = renderConfig.captionMode === "burned" ? (() => {
      const overlays: Array<{text: string; start_pct: number; end_pct: number; style: string; position: string}> = [];
      const narrationText = (item.scriptItem.voiceover_text || "").trim();
      const dialogueText = (item.scriptItem.dialogue_text || "").trim();
      const dialogueSpeaker = (item.scriptItem.dialogue_speaker || "").trim();
      const hasDialogue = dialogueText.length > 0;

      // When dialogue exists, strip it from narration to avoid duplication.
      // The TTS audio merges narration + dialogue, but subtitles should show them separately.
      let pureNarration = narrationText;
      if (hasDialogue) {
        // Remove dialogue text from narration if it appears inside it
        pureNarration = narrationText.replace(dialogueText, "").trim();
        // Also try removing common merged patterns like "Speaker nói: dialogue"
        const speakerPatterns = dialogueSpeaker
          ? [
              `${dialogueSpeaker} nói: ${dialogueText}`,
              `${dialogueSpeaker} nói ${dialogueText}`,
              `${dialogueSpeaker}: ${dialogueText}`,
            ]
          : [];
        for (const pattern of speakerPatterns) {
          if (pureNarration.includes(pattern)) {
            pureNarration = pureNarration.replace(pattern, "").trim();
          }
        }
        // Clean up trailing/leading punctuation artifacts
        pureNarration = pureNarration.replace(/[,.:;]\s*$/, "").trim();
      }

      const hasPureNarration = pureNarration.length > 0;

      // Calculate timeline split between narration and dialogue
      const narrationWords = hasPureNarration ? pureNarration.split(/\s+/).length : 0;
      const dialogueWords = hasDialogue ? dialogueText.split(/\s+/).length : 0;
      const totalWords = narrationWords + dialogueWords || 1;
      const narrationEndPct = hasDialogue ? narrationWords / totalWords : 1;

      // Narration overlays (subtitle_stroke style — bold, no background, heavy outline)
      if (hasPureNarration) {
        const chunks = item.audioChunks && item.audioChunks.length > 0 
          ? item.audioChunks 
          : pureNarration.split(/(?<=[.!?])\s+/).map((t, i) => ({ i: i + 1, text: t, w: t.split(/\s+/).length }));

        const chunkTotalWords = chunks.reduce((acc, c) => acc + (c.w || 1), 0);
        let currentPct = 0;
        for (const chunk of chunks) {
          const durationPct = ((chunk.w || 1) / chunkTotalWords) * narrationEndPct;
          overlays.push({
            text: chunk.text,
            start_pct: currentPct,
            end_pct: currentPct + durationPct,
            style: "subtitle_stroke",
            position: "bottom_center",
          });
          currentPct += durationPct;
        }
      }

      // Dialogue overlays (subtitle_stroke with speaker prefix)
      if (hasDialogue) {
        const prefix = dialogueSpeaker ? `"${dialogueSpeaker}: ` : `"`;
        const dialogueChunks = dialogueText.split(/(?<=[.!?])\s+/);
        const dialogueTotalWords = dialogueChunks.reduce((acc, t) => acc + t.split(/\s+/).length, 0);
        let currentPct = narrationEndPct;
        for (let i = 0; i < dialogueChunks.length; i++) {
          const chunk = dialogueChunks[i];
          const words = chunk.split(/\s+/).length;
          const durationPct = (words / dialogueTotalWords) * (1 - narrationEndPct);
          // Only first chunk gets speaker prefix, last chunk gets closing quote
          const isFirst = i === 0;
          const isLast = i === dialogueChunks.length - 1;
          const displayText = (isFirst ? prefix : `"`) + chunk + (isLast ? `"` : ``);
          overlays.push({
            text: displayText,
            start_pct: currentPct,
            end_pct: currentPct + durationPct,
            style: "subtitle_stroke",
            position: "bottom_center",
          });
          currentPct += durationPct;
        }
      }

      return overlays;
    })() : [];

    const clip: CompiledRenderClip = {
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
      motionIntensity,
      panel,
      imageBlob: item.imageBlob,
      audioBlob: item.audioStatus === "ready" ? item.audioBlob : undefined,
      // Effect metadata (resolved)
      sceneType: item.sceneType,
      mood: item.mood,
      transition,
      transitionDurationMs,
      vfxTags: item.vfxTags,
      sfxTags: item.sfxTags,
      subtitleMood: item.subtitleMood,
      text_overlays,
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
