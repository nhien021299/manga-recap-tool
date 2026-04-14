import { useCallback, useState } from "react";

import { generateSpeech } from "@/lib/tts/elevenLabsClient";
import { useRecapStore } from "@/shared/storage/useRecapStore";

export function useVoiceGeneration() {
  const { voiceConfig, timeline, updateTimelineItem, setIsLoading, setProgress } = useRecapStore();
  const [error, setError] = useState<string | null>(null);

  const generateAllVoices = useCallback(async () => {
    if (!voiceConfig.elevenLabsApiKey) {
      setError("Thiếu ElevenLabs API Key. Vào Cài đặt để cấu hình.");
      return;
    }

    setIsLoading(true);
    setProgress(0);
    setError(null);

    try {
      for (let index = 0; index < timeline.length; index += 1) {
        const item = timeline[index];
        if (!item.scriptItem?.voiceover_text) continue;

        const audioBlob = await generateSpeech(
          voiceConfig.elevenLabsApiKey,
          item.scriptItem.voiceover_text,
          voiceConfig.ttsVoiceId,
          voiceConfig.ttsModel
        );

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
        setProgress(Math.round(((index + 1) / timeline.length) * 100));
      }
    } catch (voiceError) {
      setError(voiceError instanceof Error ? voiceError.message : "Unknown voice generation error.");
    } finally {
      setIsLoading(false);
    }
  }, [setIsLoading, setProgress, timeline, updateTimelineItem, voiceConfig]);

  const generateSingleVoice = useCallback(
    async (index: number) => {
      const item = timeline[index];
      if (!item?.scriptItem?.voiceover_text || !voiceConfig.elevenLabsApiKey) return;

      try {
        const audioBlob = await generateSpeech(
          voiceConfig.elevenLabsApiKey,
          item.scriptItem.voiceover_text,
          voiceConfig.ttsVoiceId,
          voiceConfig.ttsModel
        );

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
      } catch (voiceError) {
        setError(voiceError instanceof Error ? voiceError.message : "Unknown voice generation error.");
      }
    },
    [timeline, updateTimelineItem, voiceConfig]
  );

  return { generateAllVoices, generateSingleVoice, error };
}
