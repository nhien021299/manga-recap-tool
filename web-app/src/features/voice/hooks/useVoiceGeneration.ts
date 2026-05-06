import { useCallback, useState } from "react";

import { generateVoiceAudio, generateVoiceBatchAudio } from "@/features/voice/api/voiceApi";
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
    (text: string, dialogue?: string | null, speaker?: string | null) => ({
      text,
      provider: voiceConfig.provider,
      voiceKey: voiceConfig.voiceKey,
      speed: voiceConfig.speed,
      dialogue,
      speaker,
    }),
    [voiceConfig]
  );

  const attachAudioToTimeline = useCallback(
    async (index: number, audioBlob: Blob, chunks?: any[]) => {
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
        audioChunks: chunks,
      });
    },
    [updateTimelineItem]
  );

  const generateVoicesByIndexes = useCallback(async (indexes: number[]) => {
    setIsLoading(true);
    setProgress(0);
    setCurrentVoiceGeneration(null);
    setError(null);

    try {
      const queuedItems = indexes
        .map((index) => ({ item: timeline[index], index }))
        .filter((entry): entry is { item: (typeof timeline)[number]; index: number } => !!entry.item)
        .filter(({ item }) => !!item.scriptItem?.voiceover_text?.trim());

      if (queuedItems.length === 0) {
        return;
      }

      queuedItems.forEach(({ index }) => updateTimelineItem(index, { audioStatus: "generating" }));
      const firstItem = queuedItems[0]!;
      setCurrentVoiceGeneration({
        currentIndex: 1,
        totalCount: queuedItems.length,
        panelId: firstItem.item.panelId,
        panelOrder: firstItem.index + 1,
        voiceKey: voiceConfig.voiceKey,
        textLength: firstItem.item.scriptItem.voiceover_text.trim().length,
        startedAt: new Date().toISOString(),
      });
      setProgress(5);

      const batchResults = await generateVoiceBatchAudio(config.apiBaseUrl, {
        provider: voiceConfig.provider,
        voiceKey: voiceConfig.voiceKey,
        speed: voiceConfig.speed,
        items: queuedItems.map(({ item, index }) => ({
          itemId: String(index),
          text: item.scriptItem.voiceover_text.trim(),
          dialogue: item.scriptItem?.dialogue_text,
          speaker: item.scriptItem?.dialogue_speaker,
        })),
      });
      const resultByIndex = new Map(batchResults.map((result) => [Number(result.itemId), result]));

      for (let queueIndex = 0; queueIndex < queuedItems.length; queueIndex += 1) {
        const { item, index } = queuedItems[queueIndex]!;
        const result = resultByIndex.get(index);
        if (!result) {
          updateTimelineItem(index, { audioStatus: "error" });
          continue;
        }

        setCurrentVoiceGeneration({
          currentIndex: queueIndex + 1,
          totalCount: queuedItems.length,
          panelId: item.panelId,
          panelOrder: index + 1,
          voiceKey: voiceConfig.voiceKey,
          textLength: item.scriptItem.voiceover_text.trim().length,
          startedAt: new Date().toISOString(),
        });
        await attachAudioToTimeline(index, result.blob, result.chunks);
        setProgress(Math.round(((queueIndex + 1) / Math.max(queuedItems.length, 1)) * 100));
      }

      // Hold 100% briefly so the user can see completion before the list view settles.
      await new Promise((resolve) => setTimeout(resolve, 600));
    } catch (voiceError) {
      indexes.forEach((index) => updateTimelineItem(index, { audioStatus: "error" }));
      setError(voiceError instanceof Error ? voiceError.message : "Unknown voice generation error.");
    } finally {
      setCurrentVoiceGeneration(null);
      setIsLoading(false);
    }
  }, [
    attachAudioToTimeline,
    config.apiBaseUrl,
    setCurrentVoiceGeneration,
    setIsLoading,
    setProgress,
    timeline,
    updateTimelineItem,
    voiceConfig.provider,
    voiceConfig.speed,
    voiceConfig.voiceKey,
  ]);

  const generateAllVoices = useCallback(async () => {
    await generateVoicesByIndexes(timeline.map((_, index) => index));
  }, [generateVoicesByIndexes, timeline]);

  const generateStaleVoices = useCallback(async () => {
    const staleIndexes = timeline
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => item.audioStatus === "stale")
      .map(({ index }) => index);

    if (staleIndexes.length === 0) return;
    await generateVoicesByIndexes(staleIndexes);
  }, [generateVoicesByIndexes, timeline]);

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
        const result = await generateVoiceAudio(
          config.apiBaseUrl, 
          buildRequest(text, item.scriptItem?.dialogue_text, item.scriptItem?.dialogue_speaker)
        );
        await attachAudioToTimeline(index, result.blob, result.chunks);
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
      delete clone.audioChunks;
      clone.audioStatus = "missing";
      return clone;
    });
    setTimeline(newTimeline);
  }, [timeline, setTimeline]);

  return { generateAllVoices, generateStaleVoices, generateSingleVoice, clearAllVoices, error };
}
