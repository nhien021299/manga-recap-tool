import { describe, expect, it } from "vitest";

import { buildRenderPlan, getTimelineClipDurationMs, validateRenderPlan } from "@/features/render/lib/renderPlan";
import type { Panel, RenderConfig, TimelineItem } from "@/shared/types";

const renderConfig: RenderConfig = {
  captionMode: "off",
  outputWidth: 1080,
  aspectRatio: 9 / 16,
};

const createPanel = (id: string): Panel => ({
  id,
  blob: new Blob([id], { type: "image/png" }),
  base64: `data:image/png;base64,${btoa(id)}`,
  thumbnail: `data:image/png;base64,${btoa(`${id}-thumb`)}`,
  width: 1080,
  height: 1600,
  order: 0,
});

const createTimelineItem = (panelId: string, overrides?: Partial<TimelineItem>): TimelineItem => ({
  panelId,
  imageBlob: new Blob([panelId], { type: "image/png" }),
  scriptItem: {
    panel_index: 1,
    voiceover_text: "Narration line",
  },
  scriptStatus: "auto",
  enabled: true,
  holdAfterMs: 250,
  audioBlob: new Blob(["audio"], { type: "audio/wav" }),
  audioDuration: 1.2,
  audioStatus: "ready",
  ...overrides,
});

describe("renderPlan", () => {
  it("computes clip duration from ready audio plus hold", () => {
    const durationMs = getTimelineClipDurationMs(createTimelineItem("panel-1", { audioDuration: 1.5, holdAfterMs: 250 }));
    expect(durationMs).toBe(1750);
  });

  it("falls back to a silent minimum duration for empty narration", () => {
    const durationMs = getTimelineClipDurationMs(
      createTimelineItem("panel-1", {
        scriptItem: { panel_index: 1, voiceover_text: "" },
        audioBlob: undefined,
        audioDuration: undefined,
        audioStatus: "missing",
        holdAfterMs: 900,
      })
    );

    expect(durationMs).toBe(1500);
  });

  it("excludes disabled clips and computes start offsets in order", () => {
    const panels = [createPanel("panel-1"), createPanel("panel-2"), createPanel("panel-3")];
    const plan = buildRenderPlan(
      [
        createTimelineItem("panel-2", { holdAfterMs: 100, audioDuration: 1 }),
        createTimelineItem("panel-1", { enabled: false }),
        createTimelineItem("panel-3", {
          holdAfterMs: 400,
          audioDuration: undefined,
          audioBlob: undefined,
          audioStatus: "missing",
          scriptItem: { panel_index: 3, voiceover_text: "" },
        }),
      ],
      panels,
      renderConfig
    );

    expect(plan.clips).toHaveLength(2);
    expect(plan.clips[0]?.panelId).toBe("panel-2");
    expect(plan.clips[0]?.startMs).toBe(0);
    expect(plan.clips[1]?.panelId).toBe("panel-3");
    expect(plan.clips[1]?.startMs).toBe(1100);
  });

  it("blocks export when narration changed and audio is stale", () => {
    const errors = validateRenderPlan(
      [createTimelineItem("panel-1", { audioStatus: "stale" })],
      [createPanel("panel-1")]
    );

    expect(errors).toContain("Clip 1 needs regenerated audio after narration edits.");
  });

  it("blocks export when narrated clip has no ready audio", () => {
    const errors = validateRenderPlan(
      [
        createTimelineItem("panel-1", {
          audioBlob: undefined,
          audioDuration: undefined,
          audioStatus: "missing",
        }),
      ],
      [createPanel("panel-1")]
    );

    expect(errors).toContain("Clip 1 is missing ready audio.");
  });
});
