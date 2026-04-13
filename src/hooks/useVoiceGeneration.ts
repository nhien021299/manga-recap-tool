import { useState, useCallback } from "react";
import { useRecapStore } from "@/store/useRecapStore";
import { generateSpeech } from "@/lib/tts/elevenLabsClient";

export function useVoiceGeneration() {
  const { config, timeline, updateTimelineItem, setIsLoading, setProgress } = useRecapStore();
  const [error, setError] = useState<string | null>(null);

  const generateAllVoices = useCallback(async () => {
    if (!config.elevenLabsApiKey) {
      setError("Thiếu ElevenLabs API Key! Vui lòng vào Cài đặt.");
      return;
    }

    setIsLoading(true);
    setProgress(0);
    setError(null);

    try {
      for (let i = 0; i < timeline.length; i++) {
        const item = timeline[i];
        if (!item.scriptItem?.voiceover_text) continue;

        // Generate speech for each timeline item
        const audioBlob = await generateSpeech(
          config.elevenLabsApiKey,
          item.scriptItem.voiceover_text,
          config.ttsVoiceId
        );

        // Calculate audio duration
        const audioUrl = URL.createObjectURL(audioBlob);
        const duration = await new Promise<number>((resolve) => {
          const audio = new Audio(audioUrl);
          audio.onloadedmetadata = () => resolve(audio.duration);
        });

        // Update state
        updateTimelineItem(i, { 
          audioBlob,
          audioUrl,
          audioDuration: duration
        });

        setProgress(Math.round(((i + 1) / timeline.length) * 100));
      }
    } catch (e: any) {
      setError(e.message);
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  }, [config, timeline, updateTimelineItem, setIsLoading, setProgress]);

  const generateSingleVoice = async (index: number) => {
    const item = timeline[index];
    if (!item.scriptItem?.voiceover_text || !config.elevenLabsApiKey) return;

    try {
      const audioBlob = await generateSpeech(
        config.elevenLabsApiKey,
        item.scriptItem.voiceover_text,
        config.ttsVoiceId
      );

      const audioUrl = URL.createObjectURL(audioBlob);
      const duration = await new Promise<number>((resolve) => {
        const audio = new Audio(audioUrl);
        audio.onloadedmetadata = () => resolve(audio.duration);
      });

      updateTimelineItem(index, { 
        audioBlob,
        audioUrl,
        audioDuration: duration
      });
    } catch (e: any) {
      setError(e.message);
    }
  };

  return { generateAllVoices, generateSingleVoice, error };
}
