import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("idb-keyval", () => ({
  get: vi.fn(async () => undefined),
  set: vi.fn(async () => undefined),
}));

import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { TimelineItem } from "@/shared/types";

const createTimelineItem = (): TimelineItem => ({
  panelId: "panel-1",
  imageBlob: new Blob(["panel"], { type: "image/png" }),
  scriptItem: {
    panel_index: 1,
    voiceover_text: "Original narration",
  },
  scriptBaseline: "Original narration",
  scriptStatus: "auto",
  enabled: true,
  holdAfterMs: 250,
  audioBlob: new Blob(["audio"], { type: "audio/wav" }),
  audioDuration: 1.25,
  audioStatus: "ready",
});

describe("useRecapStore timeline editing", () => {
  beforeEach(() => {
    localStorage.clear();
    useRecapStore.persist.clearStorage();
    useRecapStore.setState({
      timeline: [],
      scriptMeta: {
        status: "generated",
        sourceUnits: [],
        rawOutput: "",
        pipeline: "backend-gemini-unified",
      },
    });
  });

  it("marks ready audio as stale when narration changes", () => {
    useRecapStore.getState().setTimeline([createTimelineItem()]);

    useRecapStore.getState().updateTimelineItem(0, {
      scriptItem: {
        panel_index: 1,
        voiceover_text: "Edited narration",
      },
    });

    const timelineItem = useRecapStore.getState().timeline[0];
    expect(timelineItem?.scriptStatus).toBe("edited");
    expect(timelineItem?.audioStatus).toBe("stale");
    expect(timelineItem?.audioBlob).toBeUndefined();
    expect(timelineItem?.audioDuration).toBeUndefined();
    expect(useRecapStore.getState().scriptMeta.status).toBe("edited");
  });

  it("duplicates a clip without reusing generated audio", () => {
    useRecapStore.getState().setTimeline([createTimelineItem()]);

    useRecapStore.getState().duplicateTimelineItem(0);

    const timeline = useRecapStore.getState().timeline;
    expect(timeline).toHaveLength(2);
    expect(timeline[1]?.panelId).toBe("panel-1");
    expect(timeline[1]?.scriptBaseline).toBe("Original narration");
    expect(timeline[1]?.audioBlob).toBeUndefined();
    expect(timeline[1]?.audioStatus).toBe("stale");
    expect(useRecapStore.getState().scriptMeta.status).toBe("edited");
  });

  it("resets an edited clip back to the auto baseline", () => {
    useRecapStore.getState().setTimeline([createTimelineItem()]);
    useRecapStore.getState().updateTimelineItem(0, {
      scriptItem: {
        panel_index: 1,
        voiceover_text: "Edited narration",
      },
    });

    useRecapStore.getState().resetTimelineItemToAuto(0);

    const timelineItem = useRecapStore.getState().timeline[0];
    expect(timelineItem?.scriptItem.voiceover_text).toBe("Original narration");
    expect(timelineItem?.scriptStatus).toBe("auto");
    expect(timelineItem?.audioStatus).toBe("missing");
    expect(useRecapStore.getState().scriptMeta.status).toBe("generated");
  });

  it("removes a clip from the timeline", () => {
    useRecapStore.getState().setTimeline([
      createTimelineItem(),
      {
        ...createTimelineItem(),
        panelId: "panel-2",
        scriptItem: {
          panel_index: 2,
          voiceover_text: "Second narration",
        },
        scriptBaseline: "Second narration",
      },
    ]);

    useRecapStore.getState().removeTimelineItem(0);

    const timeline = useRecapStore.getState().timeline;
    expect(timeline).toHaveLength(1);
    expect(timeline[0]?.panelId).toBe("panel-2");
  });

  it("moves clips within the timeline", () => {
    useRecapStore.getState().setTimeline([
      createTimelineItem(),
      {
        ...createTimelineItem(),
        panelId: "panel-2",
        scriptItem: {
          panel_index: 2,
          voiceover_text: "Second narration",
        },
        scriptBaseline: "Second narration",
      },
    ]);

    useRecapStore.getState().moveTimelineItem(1, 0);

    const timeline = useRecapStore.getState().timeline;
    expect(timeline[0]?.panelId).toBe("panel-2");
    expect(timeline[1]?.panelId).toBe("panel-1");
  });

  it("marks generated audio as stale when voice speed changes", () => {
    useRecapStore.getState().setTimeline([createTimelineItem()]);

    useRecapStore.getState().setVoiceConfig({ speed: 1.1 });

    const timelineItem = useRecapStore.getState().timeline[0];
    expect(useRecapStore.getState().voiceConfig.speed).toBe(1.1);
    expect(timelineItem?.audioBlob).toBeUndefined();
    expect(timelineItem?.audioDuration).toBeUndefined();
    expect(timelineItem?.audioStatus).toBe("stale");
  });
});
