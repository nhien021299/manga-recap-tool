import { useState, useCallback } from "react";
import { useRecapStore } from "@/store/useRecapStore";
import { generateScriptDirect } from "@/lib/gemini/geminiClient";
import type { TimelineItem } from "@/types";

export function useScriptGeneration() {
  const { config, panels, scriptContext, setTimeline, setCurrentStep, setIsLoading, setProgress, addLog } = useRecapStore();
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateScript = useCallback(async () => {
    if (!config.geminiApiKey) {
      const msg = "Thiếu Gemini API Key! Vui lòng vào Cài đặt để thêm.";
      setError(msg);
      addLog({ type: 'error', message: msg });
      return;
    }
    
    if (!scriptContext.mangaName || !scriptContext.mainCharacter) {
      const msg = "Vui lòng nhập Tên truyện và Nhân vật chính trước khi tạo script.";
      setError(msg);
      addLog({ type: 'error', message: msg });
      return;
    }

    setIsGenerating(true);
    setIsLoading(true);
    setProgress(5);
    setError(null);

    addLog({ 
      type: 'request', 
      message: `Bắt đầu tạo kịch bản cho ${panels.length} panels — "${scriptContext.mangaName}"`,
      details: JSON.stringify({ scriptContext, panelCount: panels.length }, null, 2)
    });

    try {
      setProgress(10);
      const generatedItems = await generateScriptDirect(
        config.geminiApiKey, 
        panels, 
        scriptContext,
        (type, message, details) => {
          addLog({ type, message, details });
          // Bump progress on each log event to show liveness
          const currentProgress = useRecapStore.getState().progress;
          setProgress(Math.min(currentProgress + 5, 90));
        }
      );
      
      setProgress(95);

      addLog({ 
        type: 'result', 
        message: `✅ Tổng hợp hoàn tất: ${generatedItems.length}/${panels.length} scenes.`,
        details: JSON.stringify(generatedItems, null, 2)
      });

      // Map generated JSON to TimelineItems
      const timeline: TimelineItem[] = panels.map((panel, index) => {
        const itemIndex = index + 1;
        const scriptItem = generatedItems.find(item => item.panel_index === itemIndex) || {
          panel_index: itemIndex,
          ai_view: "Không có mô tả",
          voiceover_text: "...",
          sfx: []
        };
        
        return {
          panelId: panel.id,
          imageBlob: panel.blob,
          scriptItem
        };
      });

      // Extract unique SFX keywords and update dictionary
      const allSfx = new Set<string>();
      generatedItems.forEach(item => {
        if (Array.isArray(item.sfx)) {
          item.sfx.forEach(tag => allSfx.add(tag));
        }
      });
      if (allSfx.size > 0) {
        useRecapStore.getState().addSFXToDictionary(Array.from(allSfx));
      }

      setTimeline(timeline);
      setProgress(100);
      setCurrentStep('script');
    } catch (e: any) {
      if (e.message?.includes("[Parse Error]")) {
        setError("AI trả về kết quả bị cắt cụt. Hãy xem Log để lấy nội dung thô hoặc thử chạy lại.");
        addLog({ type: 'error', message: 'Lỗi cắt ngang nội dung (Max Output Tokens)', details: e.message });
      } else {
        setError(e.message || "Lỗi từ Gemini API. Xem log để biết chi tiết.");
        addLog({ type: 'error', message: 'API Error', details: e.message });
      }
      console.error(e);
    } finally {
      setIsGenerating(false);
      setIsLoading(false);
    }
  }, [config.geminiApiKey, panels, scriptContext, setTimeline, setCurrentStep, setIsLoading, setProgress, addLog]);

  return { generateScript, isGenerating, error };
}
