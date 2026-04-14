import { useCallback, useEffect, useRef, useState } from "react";

import {
  cancelScriptJob,
  createScriptJob,
  getScriptJobResult,
  getScriptJobStatus,
} from "@/features/script/api/scriptApi";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { Panel, ScriptItem, StoryMemory, TimelineItem } from "@/shared/types";

const POLL_INTERVAL_MS = 1500;
const SCRIPT_CHUNK_SIZE = 10;

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
    scriptJob,
    setScriptJob,
  } = useRecapStore();
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<number | null>(null);
  const syncInFlightRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const applyCompletedResult = useCallback(
    async (jobId: string) => {
      const result = await getScriptJobResult(config.apiBaseUrl, jobId);

      setPanelUnderstandings(result.understandings);
      setPanelUnderstandingMeta({
        generatedAt: new Date().toISOString(),
        panelSignature: result.panelSignature,
        rawOutput: result.rawOutputs?.understanding || "",
      });
      setStoryMemories(result.storyMemories);

      const nextTimeline = mergeTimelineWithExisting(panels, result.generatedItems, timeline, result.storyMemories);
      const allSfx = new Set<string>();
      result.generatedItems.forEach((item) => {
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
        rawOutput: result.rawOutputs?.script || "",
        pipeline: "backend-caption-memory",
      });
      setProgress(100);
      setCurrentStep("script");
      setScriptJob({
        status: "completed",
        progress: 100,
        resultReady: true,
        error: undefined,
      });
    },
    [
      addSFXToDictionary,
      config.apiBaseUrl,
      panels,
      setCurrentStep,
      setPanelUnderstandingMeta,
      setPanelUnderstandings,
      setProgress,
      setScriptJob,
      setScriptMeta,
      setStoryMemories,
      setTimeline,
      timeline,
    ]
  );

  const syncJob = useCallback(
    async (jobId: string) => {
      if (syncInFlightRef.current) return;
      syncInFlightRef.current = true;
      try {
        const status = await getScriptJobStatus(config.apiBaseUrl, jobId);
        replaceLogs(
          status.logs.map((log) => ({
            type: log.type,
            message: log.message,
            details: log.details,
          }))
        );

        const progress = Math.max(status.progress, scriptJob.progress || 0);
        setProgress(progress);
        setScriptJob({
          jobId: status.jobId,
          status: status.status,
          progress,
          error: status.error || undefined,
          resultReady: status.status === "completed",
        });

        if (status.status === "completed") {
          stopPolling();
          await applyCompletedResult(jobId);
          setIsLoading(false);
        } else if (status.status === "failed" || status.status === "cancelled") {
          stopPolling();
          setError(status.error || "Script job failed.");
          setIsLoading(false);
        }
      } catch (jobError) {
        stopPolling();
        setError(jobError instanceof Error ? jobError.message : "Unknown backend error.");
        setIsLoading(false);
      } finally {
        syncInFlightRef.current = false;
      }
    },
    [
      applyCompletedResult,
      config.apiBaseUrl,
      replaceLogs,
      scriptJob.progress,
      setIsLoading,
      setProgress,
      setScriptJob,
      stopPolling,
    ]
  );

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();
      pollingRef.current = window.setInterval(() => {
        void syncJob(jobId);
      }, POLL_INTERVAL_MS);
      void syncJob(jobId);
    },
    [stopPolling, syncJob]
  );

  const generateScript = useCallback(async () => {
    if (panels.length === 0) {
      const message = "No extracted panels available. Return to Extract before generating script.";
      setError(message);
      addLog({ type: "error", message });
      return;
    }
    if (!config.apiBaseUrl) {
      const message = "Missing ai-backend URL. Check Settings.";
      setError(message);
      addLog({ type: "error", message });
      return;
    }
    if (!scriptContext.mangaName || !scriptContext.mainCharacter) {
      const message = "Please provide manga name and main character before generating script.";
      setError(message);
      addLog({ type: "error", message });
      return;
    }

    setError(null);
    setIsLoading(true);
    setProgress(5);
    replaceLogs([]);
    addLog({
      type: "request",
      message: `Submitting backend script job for ${panels.length} panels`,
      details: JSON.stringify(
        {
          apiBaseUrl: config.apiBaseUrl,
          panelCount: panels.length,
          language: config.language,
        },
        null,
        2
      ),
    });

    try {
      const created = await createScriptJob(config.apiBaseUrl, panels, {
        ...scriptContext,
        language: config.language,
      });
      setScriptJob({
        jobId: created.jobId,
        status: created.status as "queued",
        progress: 10,
        error: undefined,
        resultReady: false,
      });
      startPolling(created.jobId);
    } catch (jobError) {
      setIsLoading(false);
      const message = jobError instanceof Error ? jobError.message : "Unknown backend error.";
      setError(message);
      addLog({ type: "error", message: "Failed to create script job", details: message });
    }
  }, [
    addLog,
    config.apiBaseUrl,
    config.language,
    panels,
    replaceLogs,
    scriptContext,
    setIsLoading,
    setProgress,
    setScriptJob,
    startPolling,
  ]);

  const cancelActiveScriptJob = useCallback(async () => {
    if (!scriptJob.jobId) return;
    try {
      const status = await cancelScriptJob(config.apiBaseUrl, scriptJob.jobId);
      stopPolling();
      setScriptJob({
        jobId: status.jobId,
        status: status.status,
        progress: status.progress,
        error: status.error || undefined,
      });
      setIsLoading(false);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Unknown cancellation error.");
    }
  }, [config.apiBaseUrl, scriptJob.jobId, setIsLoading, setScriptJob, stopPolling]);

  useEffect(() => {
    if (scriptJob.jobId && (scriptJob.status === "queued" || scriptJob.status === "running")) {
      setIsLoading(true);
      startPolling(scriptJob.jobId);
    }
    return () => {
      stopPolling();
    };
  }, [scriptJob.jobId, scriptJob.status, setIsLoading, startPolling, stopPolling]);

  return {
    generateScript,
    cancelActiveScriptJob,
    isGenerating: scriptJob.status === "queued" || scriptJob.status === "running",
    error,
  };
}
