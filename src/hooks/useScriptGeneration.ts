import { useState, useCallback } from "react";
import { useRecapStore } from "@/store/useRecapStore";
import { generateScriptDirect } from "@/lib/gemini/geminiClient";
import type { TimelineItem } from "@/types";

export function useScriptGeneration() {
  const { config, panels, scriptContext, setTimeline, setCurrentStep, setIsLoading, setProgress } = useRecapStore();
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateScript = useCallback(async () => {
    if (!config.geminiApiKey) {
      setError("Thiếu Gemini API Key! Vui lòng vào Cài đặt để thêm.");
      return;
    }
    
    if (!scriptContext.mangaName || !scriptContext.mainCharacter) {
      setError("Vui lòng nhập Tên truyện và Nhân vật chính trước khi tạo script.");
      return;
    }

    setIsGenerating(true);
    setIsLoading(true);
    setProgress(20);
    setError(null);

    try {
      setProgress(50);
      const generatedItems = await generateScriptDirect(config.geminiApiKey, panels, scriptContext);
      
      setProgress(80);

      // Map generated JSON to TimelineItems
      // Gemini returns panel_index (1-based), so we match carefully
      const timeline: TimelineItem[] = panels.map((panel, index) => {
        const itemIndex = index + 1;
        const scriptItem = generatedItems.find(item => item.panel_index === itemIndex) || {
          panel_index: itemIndex,
          ai_view: "Không có mô tả",
          speaker: "",
          dialogue: "",
          narration: "...",
          sfx: ""
        };
        
        return {
          panelId: panel.id,
          imageBlob: panel.blob,
          scriptItem
        };
      });

      setTimeline(timeline);
      setProgress(100);
      setCurrentStep('script');
    } catch (e: any) {
      setError(e.message);
      console.error(e);
    } finally {
      setIsGenerating(false);
      setIsLoading(false);
    }
  }, [config.geminiApiKey, panels, scriptContext, setTimeline, setCurrentStep, setIsLoading, setProgress]);

  return { generateScript, isGenerating, error };
}
