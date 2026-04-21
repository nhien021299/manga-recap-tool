import { useCallback, useState } from "react";

import { generateVoiceAudio } from "@/features/voice/api/voiceApi";
import { useRecapStore } from "@/shared/storage/useRecapStore";

export function useVoiceGeneration() {
  const { config, voiceConfig, timeline, updateTimelineItem, setIsLoading, setProgress, setTimeline } = useRecapStore();
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
      const audioUrl = URL.createObjectURL(audioBlob);
      const duration = await new Promise<number>((resolve) => {
        const audio = new Audio(audioUrl);
        audio.onloadedmetadata = () => resolve(audio.duration);
      });

      updateTimelineItem(index, {
        audioBlob,
        audioUrl,
        audioDuration: duration,
      });
    },
    [updateTimelineItem]
  );

  const generateAllVoices = useCallback(async () => {
    setIsLoading(true);
    setProgress(0);
    setError(null);

    try {
      for (let index = 0; index < timeline.length; index += 1) {
        const item = timeline[index];
        if (!item.scriptItem?.voiceover_text) continue;

        const audioBlob = await generateVoiceAudio(config.apiBaseUrl, buildRequest(item.scriptItem.voiceover_text));
        await attachAudioToTimeline(index, audioBlob);
        setProgress(Math.round(((index + 1) / timeline.length) * 100));
      }
      // Ngâm trạng thái 100% để user nhìn thấy một chút trước khi văng sang màn list
      await new Promise((resolve) => setTimeout(resolve, 600));
    } catch (voiceError) {
      setError(voiceError instanceof Error ? voiceError.message : "Unknown voice generation error.");
    } finally {
      setIsLoading(false);
    }
  }, [attachAudioToTimeline, buildRequest, config.apiBaseUrl, setIsLoading, setProgress, timeline]);

  const generateSingleVoice = useCallback(
    async (index: number) => {
      const item = timeline[index];
      if (!item?.scriptItem?.voiceover_text) return;

      try {
        setError(null);
        const audioBlob = await generateVoiceAudio(config.apiBaseUrl, buildRequest(item.scriptItem.voiceover_text));
        await attachAudioToTimeline(index, audioBlob);
      } catch (voiceError) {
        setError(voiceError instanceof Error ? voiceError.message : "Unknown voice generation error.");
      }
    },
    [attachAudioToTimeline, buildRequest, config.apiBaseUrl, timeline]
  );

  const clearAllVoices = useCallback(() => {
    const newTimeline = timeline.map((item) => {
      const clone = { ...item };
      delete clone.audioBlob;
      delete clone.audioUrl;
      delete clone.audioDuration;
      return clone;
    });
    setTimeline(newTimeline);
  }, [timeline, setTimeline]);

  return { generateAllVoices, generateSingleVoice, clearAllVoices, error };
}
