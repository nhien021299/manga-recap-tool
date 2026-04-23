import { useCallback, useRef, useState } from "react";

import { submitScriptGeneration } from "@/features/script/api/scriptApi";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { Panel, ScriptItem, StoryMemory, TimelineItem } from "@/shared/types";

const SCRIPT_CHUNK_SIZE = 10;

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
      voiceover_text: "Narration unavailable.",
    };
    const existing = existingByPanelId.get(panel.id);
    const memoryForPanel = storyMemories[Math.floor(index / SCRIPT_CHUNK_SIZE)];

    if (existing?.scriptStatus === "edited") {
      return {
        ...existing,
        panelId: panel.id,
        imageBlob: panel.blob,
        scriptBaseline: generated.voiceover_text,
        scriptSource: {
          panelId: panel.id,
          orderIndex: index,
        },
        scriptSegment: {
          narration: generated.voiceover_text,
          status: "auto",
          memorySnapshot: memoryForPanel?.summary,
        },
      };
    }

    const generatedText = generated.voiceover_text.trim();
    const canReuseAudio =
      !!existing &&
      (existing.scriptItem.voiceover_text ?? "").trim() === generatedText &&
      existing.audioStatus === "ready" &&
      !!existing.audioBlob;

    const nextItem: TimelineItem = {
      panelId: panel.id,
      imageBlob: panel.blob,
      scriptItem: generated,
      scriptBaseline: generated.voiceover_text,
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
      enabled: existing?.enabled ?? true,
      holdAfterMs: existing?.holdAfterMs ?? 250,
    };

    if (canReuseAudio && existing) {
      nextItem.audioBlob = existing.audioBlob;
      nextItem.audioDuration = existing.audioDuration;
      nextItem.audioStatus = "ready";
      return nextItem;
    }

    nextItem.audioStatus = generatedText ? "missing" : "missing";
    return nextItem;
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
    addLog,
    replaceLogs,
  } = useRecapStore();

  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const activeRequestId = useRef(0);

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
    const requestId = activeRequestId.current + 1;
    activeRequestId.current = requestId;

    setError(null);
    setIsGenerating(true);
    setIsLoading(true);
    setProgress(10);
    replaceLogs([]);
    log(
      "request",
      `Starting Gemini script generation for ${panels.length} panels.`,
      JSON.stringify(
        {
          panelCount: panels.length,
          language: config.language,
          endpoint: "/api/v1/script/generate",
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

      const response = await submitScriptGeneration(config.apiBaseUrl, panels, context, {
        reuseCache: true,
        returnRawOutputs: true,
      });

      if (activeRequestId.current !== requestId) {
        return;
      }

      replaceLogs(response.logs || []);

      if (response.error) {
        throw new Error(response.error);
      }

      const finalResult = response.result;
      if (!finalResult) {
        throw new Error("Backend returned no script result.");
      }

      setPanelUnderstandings(finalResult.understandings || []);
      setPanelUnderstandingMeta({
        generatedAt: new Date().toISOString(),
        panelSignature: buildPanelSignature(panels),
        rawOutput: finalResult.rawOutputs?.understanding || "",
      });

      setStoryMemories(finalResult.storyMemories || []);

      const nextTimeline = mergeTimelineWithExisting(
        panels,
        finalResult.generatedItems || [],
        timeline,
        finalResult.storyMemories || []
      );

      setTimeline(nextTimeline);
      setScriptMeta({
        status: nextTimeline.some((item) => item.scriptStatus === "edited") ? "edited" : "generated",
        sourceUnits: panels.map((panel, index) => ({
          panelId: panel.id,
          orderIndex: index,
        })),
        generatedAt: new Date().toISOString(),
        rawOutput: finalResult.rawOutputs?.script || "",
        pipeline: "backend-gemini-unified",
        metrics: finalResult.metrics,
      });

      setProgress(100);
      setCurrentStep("script");
      log("result", "Gemini script generation completed.", JSON.stringify(finalResult.metrics, null, 2));
    } catch (generationError) {
      if (activeRequestId.current !== requestId) {
        return;
      }

      const message = generationError instanceof Error ? generationError.message : "Unknown backend Gemini error.";
      setError(message);
      log("error", "Backend Gemini script generation failed", message);
    } finally {
      if (activeRequestId.current === requestId) {
        setIsGenerating(false);
        setIsLoading(false);
      }
    }
  }, [
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

  const cancelActiveScriptJob = useCallback(async () => {
    activeRequestId.current += 1;
    setIsGenerating(false);
    setIsLoading(false);
    log("request", "Ignored the active script response on the frontend.");
  }, [log, setIsLoading]);

  return {
    generateScript,
    cancelActiveScriptJob,
    isGenerating,
    canCancel: isGenerating,
    error,
  };
}
