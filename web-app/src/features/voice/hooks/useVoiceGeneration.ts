import { useCallback, useState } from "react";

import { generateVoiceAudio } from "@/features/voice/api/voiceApi";
import { useRecapStore } from "@/shared/storage/useRecapStore";

export function useVoiceGeneration() {
  const {
    config,
    voiceConfig,
    timeline,
    updateTimelineItem,
    setIsLoading,
    setProgress,
    setTimeline,
    setCurrentVoiceGeneration,
  } = useRecapStore();
  const [error, setError] = useState<string | null>(null);

  const buildRequest = useCallback(
    (text: string) => ({
      text,
      provider: voiceConfig.provider,
      voiceKey: voiceConfig.voiceKey,
      speed: voiceConfig.speed,
    }),
    [voiceConfig]
  );

  const attachAudioToTimeline = useCallback(
    async (index: number, audioBlob: Blob) => {
      const tempAudioUrl = URL.createObjectURL(audioBlob);
      const duration = await new Promise<number>((resolve) => {
        const audio = new Audio(tempAudioUrl);
        audio.onloadedmetadata = () => resolve(audio.duration);
      });
      URL.revokeObjectURL(tempAudioUrl);

      updateTimelineItem(index, {
        audioBlob,
        audioDuration: duration,
        audioStatus: "ready",
      });
    },
    [updateTimelineItem]
  );

  const generateAllVoices = useCallback(async () => {
    setIsLoading(true);
    setProgress(0);
    setCurrentVoiceGeneration(null);
    setError(null);

    try {
      const queuedItems = timeline
        .map((item, index) => ({ item, index }))
        .filter(({ item }) => !!item.scriptItem?.voiceover_text?.trim());

      for (let index = 0; index < timeline.length; index += 1) {
        const item = timeline[index];
        const text = item.scriptItem?.voiceover_text?.trim();
        if (!text) continue;

        const queuedIndex = queuedItems.findIndex((entry) => entry.index === index);
        setCurrentVoiceGeneration({
          currentIndex: queuedIndex + 1,
          totalCount: queuedItems.length,
          panelId: item.panelId,
          panelOrder: index + 1,
          voiceKey: voiceConfig.voiceKey,
          textLength: text.length,
          startedAt: new Date().toISOString(),
        });

        updateTimelineItem(index, { audioStatus: "generating" });
        const audioBlob = await generateVoiceAudio(config.apiBaseUrl, buildRequest(text));
        await attachAudioToTimeline(index, audioBlob);
        setProgress(Math.round(((index + 1) / timeline.length) * 100));
      }

      // Hold 100% briefly so the user can see completion before the list view settles.
      await new Promise((resolve) => setTimeout(resolve, 600));
    } catch (voiceError) {
      const failedIndex = timeline.findIndex((item) => item.audioStatus === "generating");
      if (failedIndex >= 0) {
        updateTimelineItem(failedIndex, { audioStatus: "error" });
      }
      setError(voiceError instanceof Error ? voiceError.message : "Unknown voice generation error.");
    } finally {
      setCurrentVoiceGeneration(null);
      setIsLoading(false);
    }
  }, [
    attachAudioToTimeline,
    buildRequest,
    config.apiBaseUrl,
    setCurrentVoiceGeneration,
    setIsLoading,
    setProgress,
    timeline,
    updateTimelineItem,
    voiceConfig.voiceKey,
  ]);

  const generateSingleVoice = useCallback(
    async (index: number) => {
      const item = timeline[index];
      if (!item?.scriptItem?.voiceover_text) return;

      try {
        const text = item.scriptItem.voiceover_text.trim();
        setError(null);
        setCurrentVoiceGeneration({
          currentIndex: 1,
          totalCount: 1,
          panelId: item.panelId,
          panelOrder: index + 1,
          voiceKey: voiceConfig.voiceKey,
          textLength: text.length,
          startedAt: new Date().toISOString(),
        });
        updateTimelineItem(index, { audioStatus: "generating" });
        const audioBlob = await generateVoiceAudio(config.apiBaseUrl, buildRequest(text));
        await attachAudioToTimeline(index, audioBlob);
      } catch (voiceError) {
        updateTimelineItem(index, { audioStatus: "error" });
        setError(voiceError instanceof Error ? voiceError.message : "Unknown voice generation error.");
      } finally {
        setCurrentVoiceGeneration(null);
      }
    },
    [attachAudioToTimeline, buildRequest, config.apiBaseUrl, setCurrentVoiceGeneration, timeline, updateTimelineItem, voiceConfig.voiceKey]
  );

  const clearAllVoices = useCallback(() => {
    const newTimeline = timeline.map((item) => {
      const clone = { ...item };
      delete clone.audioBlob;
      delete clone.audioUrl;
      delete clone.audioDuration;
      clone.audioStatus = "missing";
      return clone;
    });
    setTimeline(newTimeline);
  }, [timeline, setTimeline]);

  return { generateAllVoices, generateSingleVoice, clearAllVoices, error };
}
