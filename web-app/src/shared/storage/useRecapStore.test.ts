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
});
