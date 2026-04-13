import { useState, useCallback } from "react";
import { useRecapStore } from "@/store/useRecapStore";
import { generateScriptDirect } from "@/lib/gemini/geminiClient";
import type { TimelineItem, ScriptItem } from "@/types";

const normalizeSecret = (value: string | undefined | null): string => {
  if (!value) return "";
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
};

const isAuthKeyError = (message: string): boolean => {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("api key") ||
    normalized.includes("expired") ||
    normalized.includes("invalid") ||
    normalized.includes("permission_denied") ||
    normalized.includes("unauthenticated")
  );
};

export function useScriptGeneration() {
  const {
    config,
    panels,
    scriptContext,
    setTimeline,
    setCurrentStep,
    setIsLoading,
    setProgress,
    addLog,
  } = useRecapStore();
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateScript = useCallback(async () => {
    const storeKey = normalizeSecret(config.geminiApiKey);
    const envKey = normalizeSecret(import.meta.env.VITE_GEMINI_API_KEY || "");
    const keyCandidates = Array.from(new Set([storeKey, envKey].filter(Boolean)));

    if (keyCandidates.length === 0) {
      const msg = "Thiếu Gemini API Key! Vui lòng vào Cài đặt để thêm.";
      setError(msg);
      addLog({ type: "error", message: msg });
      return;
    }

    if (!scriptContext.mangaName || !scriptContext.mainCharacter) {
      const msg = "Vui lòng nhập Tên truyện và Nhân vật chính trước khi tạo script.";
      setError(msg);
      addLog({ type: "error", message: msg });
      return;
    }

    setIsGenerating(true);
    setIsLoading(true);
    setProgress(5);
    setError(null);

    addLog({
      type: "request",
      message: `Bắt đầu tạo kịch bản cho ${panels.length} panels - "${scriptContext.mangaName}"`,
      details: JSON.stringify({ scriptContext, panelCount: panels.length }, null, 2),
    });

    try {
      setProgress(10);

      let generatedItems: ScriptItem[] | null = null;
      let lastError: unknown = null;

      for (let i = 0; i < keyCandidates.length; i++) {
        const activeKey = keyCandidates[i];
        const source = activeKey === storeKey ? "settings/local" : "env";
        try {
          addLog({
            type: "request",
            message: `Đang gọi Gemini với key từ ${source}${keyCandidates.length > 1 ? ` (${i + 1}/${keyCandidates.length})` : ""}.`,
          });

          generatedItems = await generateScriptDirect(activeKey, panels, scriptContext, (type, message, details) => {
            addLog({ type, message, details });
            const currentProgress = useRecapStore.getState().progress;
            setProgress(Math.min(currentProgress + 5, 90));
          });
          break;
        } catch (attemptError: any) {
          lastError = attemptError;
          const retryableAuthError = isAuthKeyError(String(attemptError?.message || ""));
          const hasAnotherKey = i < keyCandidates.length - 1;

          if (!retryableAuthError || !hasAnotherKey) {
            throw attemptError;
          }

          addLog({
            type: "error",
            message: `Key ${source} bị từ chối (${attemptError?.message || "unknown error"}). Tự động thử key nguồn còn lại.`,
          });
        }
      }

      if (!generatedItems) {
        throw lastError || new Error("Không thể tạo script do lỗi API key.");
      }

      setProgress(95);

      addLog({
        type: "result",
        message: `Tong hop hoan tat: ${generatedItems.length}/${panels.length} scenes.`,
        details: JSON.stringify(generatedItems, null, 2),
      });

      const timeline: TimelineItem[] = panels.map((panel, index) => {
        const itemIndex = index + 1;
        const scriptItem = generatedItems.find((item) => item.panel_index === itemIndex) || {
          panel_index: itemIndex,
          ai_view: "Khong co mo ta",
          voiceover_text: "...",
          sfx: [],
        };

        return {
          panelId: panel.id,
          imageBlob: panel.blob,
          scriptItem,
        };
      });

      const allSfx = new Set<string>();
      generatedItems.forEach((item) => {
        if (Array.isArray(item.sfx)) {
          item.sfx.forEach((tag) => allSfx.add(tag));
        }
      });
      if (allSfx.size > 0) {
        useRecapStore.getState().addSFXToDictionary(Array.from(allSfx));
      }

      setTimeline(timeline);
      setProgress(100);
      setCurrentStep("script");
    } catch (e: any) {
      if (e.message?.includes("[Parse Error]")) {
        setError("AI trả về kết quả bị cắt cụt. Hãy xem Log để lấy nội dung thô hoặc thử chạy lại.");
        addLog({
          type: "error",
          message: "Lỗi cắt ngang nội dung (Max Output Tokens)",
          details: e.message,
        });
      } else {
        setError(e.message || "Lỗi từ Gemini API. Xem log để biết chi tiết.");
        addLog({ type: "error", message: "API Error", details: e.message });
      }
      console.error(e);
    } finally {
      setIsGenerating(false);
      setIsLoading(false);
    }
  }, [config.geminiApiKey, panels, scriptContext, setTimeline, setCurrentStep, setIsLoading, setProgress, addLog]);

  return { generateScript, isGenerating, error };
}
