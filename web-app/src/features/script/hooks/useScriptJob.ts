import { useCallback, useState } from "react";

import { generateScriptViaBackend } from "@/features/script/api/scriptApi";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { Panel, ScriptItem, StoryMemory, TimelineItem } from "@/shared/types";

const SCRIPT_CHUNK_SIZE = 20;

const buildPanelSignature = (panels: Panel[]): string =>
  JSON.stringify(
    panels.map((panel) => ({
      id: panel.id,
      width: panel.width,
      height: panel.height,
      order: panel.order,
    }))
  );

const mergeTimelineWithExisting = (
  panels: Panel[],
  generatedItems: ScriptItem[],
  existingTimeline: TimelineItem[],
  storyMemories: StoryMemory[]
): TimelineItem[] => {
  const existingByPanelId = new Map(existingTimeline.map((item) => [item.panelId, item]));

  return panels.map((panel, index) => {
    const generated = generatedItems.find((item) => item.panel_index === index + 1) || {
      panel_index: index + 1,
      ai_view: "No visual summary",
      voiceover_text: "Narration unavailable.",
      sfx: [],
    };
    const existing = existingByPanelId.get(panel.id);
    const memoryForPanel = storyMemories[Math.floor(index / SCRIPT_CHUNK_SIZE)];

    if (existing?.scriptStatus === "edited") {
      return {
        ...existing,
        panelId: panel.id,
        imageBlob: panel.blob,
        scriptSource: {
          panelId: panel.id,
          orderIndex: index,
        },
        scriptSegment: {
          narration: existing.scriptItem.voiceover_text ?? "",
          status: "edited",
          memorySnapshot: memoryForPanel?.summary,
        },
      };
    }

    return {
      panelId: panel.id,
      imageBlob: panel.blob,
      scriptItem: generated,
      scriptSource: {
        panelId: panel.id,
        orderIndex: index,
      },
      scriptSegment: {
        narration: generated.voiceover_text,
        status: "auto",
        memorySnapshot: memoryForPanel?.summary,
      },
      scriptStatus: "auto",
    };
  });
};

export function useScriptJob() {
  const {
    config,
    panels,
    timeline,
    scriptContext,
    setPanelUnderstandings,
    setPanelUnderstandingMeta,
    setStoryMemories,
    setTimeline,
    setScriptMeta,
    setCurrentStep,
    setIsLoading,
    setProgress,
    addSFXToDictionary,
    addLog,
    replaceLogs,
  } = useRecapStore();
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const log = useCallback(
    (type: "request" | "result" | "error", message: string, details?: string) => {
      addLog({ type, message, details });
    },
    [addLog]
  );

  const generateScript = useCallback(async () => {
    if (panels.length === 0) {
      const message = "No extracted panels available. Return to Extract before generating script.";
      setError(message);
      log("error", message);
      return;
    }
    if (!config.apiBaseUrl) {
      const message = "Missing backend API base URL. Open Settings and enter a valid backend URL.";
      setError(message);
      log("error", message);
      return;
    }
    if (!scriptContext.mangaName || !scriptContext.mainCharacter) {
      const message = "Please provide manga name and main character before generating script.";
      setError(message);
      log("error", message);
      return;
    }

    setError(null);
    setIsGenerating(true);
    setIsLoading(true);
    setProgress(5);
    replaceLogs([]);
    log(
      "request",
      `Starting backend Gemini script generation for ${panels.length} panels`,
      JSON.stringify(
        {
          panelCount: panels.length,
          language: config.language,
          apiBaseUrl: config.apiBaseUrl,
        },
        null,
        2
      )
    );

    try {
      const context = {
        ...scriptContext,
        language: config.language,
      } as const;
      const response = await generateScriptViaBackend(config.apiBaseUrl, panels, context, {
        reuseCache: true,
        returnRawOutputs: true,
      });
      replaceLogs(response.logs);

      setPanelUnderstandings(response.result.understandings);
      setPanelUnderstandingMeta({
        generatedAt: new Date().toISOString(),
        panelSignature: buildPanelSignature(panels),
        rawOutput: response.result.rawOutputs?.understanding || "",
      });
      setProgress(60);
      setStoryMemories(response.result.storyMemories);

      const nextTimeline = mergeTimelineWithExisting(
        panels,
        response.result.generatedItems,
        timeline,
        response.result.storyMemories
      );
      const allSfx = new Set<string>();
      response.result.generatedItems.forEach((item) => {
        (item.sfx || []).forEach((tag) => allSfx.add(tag));
      });
      if (allSfx.size > 0) {
        addSFXToDictionary(Array.from(allSfx));
      }

      setTimeline(nextTimeline);
      setScriptMeta({
        status: nextTimeline.some((item) => item.scriptStatus === "edited") ? "edited" : "generated",
        sourceUnits: panels.map((panel, index) => ({
          panelId: panel.id,
          orderIndex: index,
        })),
        generatedAt: new Date().toISOString(),
        rawOutput: response.result.rawOutputs?.script || "",
        pipeline: "backend-gemini",
      });
      setProgress(100);
      setCurrentStep("script");
      log(
        "result",
        "Backend Gemini script generation completed",
        JSON.stringify(response.result.metrics, null, 2)
      );
    } catch (generationError) {
      const message = generationError instanceof Error ? generationError.message : "Unknown backend Gemini error.";
      setError(message);
      log("error", "Backend Gemini script generation failed", message);
    } finally {
      setIsGenerating(false);
      setIsLoading(false);
    }
  }, [
    addSFXToDictionary,
    config.apiBaseUrl,
    config.language,
    log,
    panels,
    replaceLogs,
    scriptContext,
    setCurrentStep,
    setIsLoading,
    setPanelUnderstandings,
    setPanelUnderstandingMeta,
    setProgress,
    setScriptMeta,
    setStoryMemories,
    setTimeline,
    timeline,
  ]);

  const cancelActiveScriptJob = useCallback(() => {
    setError("Synchronous backend Gemini generation cannot be cancelled mid-request yet.");
  }, []);

  return {
    generateScript,
    cancelActiveScriptJob,
    isGenerating,
    canCancel: false,
    error,
  };
}
