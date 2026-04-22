import { useMemo, useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Save,
  Trash2,
  Wand2,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ScriptLogs } from "@/features/script/components/ScriptLogs";
import { useScriptJob } from "@/features/script/hooks/useScriptJob";
import { createBenchmarkRecord } from "@/features/benchmark/lib/benchmarkScore";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { Metrics } from "@/shared/types";

const parseMetricsFromLogDetails = (details?: string | null): Metrics | null => {
  if (!details) return null;
  try {
    const parsed = JSON.parse(details) as Partial<Metrics>;
    if (!parsed || typeof parsed !== "object") return null;
    if (typeof parsed.panelCount !== "number" || typeof parsed.totalMs !== "number") return null;

    return {
      panelCount: parsed.panelCount,
      totalMs: parsed.totalMs,
      captionMs: parsed.captionMs ?? 0,
      ocrMs: parsed.ocrMs ?? 0,
      mergeMs: parsed.mergeMs ?? 0,
      scriptMs: parsed.scriptMs ?? 0,
      avgPanelMs: parsed.avgPanelMs ?? 0,
      captionSource: parsed.captionSource ?? "unknown",
      totalPromptTokens: parsed.totalPromptTokens ?? 0,
      totalCandidatesTokens: parsed.totalCandidatesTokens ?? 0,
      totalTokens: parsed.totalTokens ?? 0,
      batchSizeUsed: parsed.batchSizeUsed ?? 0,
      retryCount: parsed.retryCount ?? 0,
      rateLimitedCount: parsed.rateLimitedCount ?? 0,
      throttleWaitMs: parsed.throttleWaitMs ?? 0,
      identityOcrMs: parsed.identityOcrMs ?? 0,
      identityConfirmedCount: parsed.identityConfirmedCount ?? 0,
    };
  } catch {
    return null;
  }
};

export function StepScript() {
  const {
    config,
    logs,
    timeline,
    panels,
    virtualStrip,
    panelUnderstandings,
    panelUnderstandingMeta,
    storyMemories,
    scriptMeta,
    scriptContext,
    setScriptContext,
    updateTimelineItem,
    addBenchmarkRecord,
    setCurrentStep,
    clearScriptData,
    isLoading,
  } = useRecapStore();
  const { generateScript, error, isGenerating } = useScriptJob();
  const [zoomedIdx, setZoomedIdx] = useState<number | null>(null);

  const navigateZoom = useCallback((dir: number) => {
    if (zoomedIdx === null) return;
    const nextIdx = (zoomedIdx + dir + timeline.length) % timeline.length;
    setZoomedIdx(nextIdx);
  }, [timeline.length, zoomedIdx]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (zoomedIdx === null) return;
      if (e.key === "ArrowRight") navigateZoom(1);
      if (e.key === "ArrowLeft") navigateZoom(-1);
      if (e.key === "Escape") setZoomedIdx(null);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [navigateZoom, zoomedIdx]);

  const panelById = useMemo(() => new Map(panels.map((panel) => [panel.id, panel])), [panels]);
  const latestErrorDetails = useMemo(() => {
    for (let index = logs.length - 1; index >= 0; index -= 1) {
      const log = logs[index];
      if (log.type === "error" && log.details) return log.details;
    }
    return null;
  }, [logs]);
  const availableMetrics = useMemo(() => {
    if (scriptMeta.metrics) return scriptMeta.metrics;

    for (let index = logs.length - 1; index >= 0; index -= 1) {
      const log = logs[index];
      if (log.type !== "result") continue;
      if (!log.message.toLowerCase().includes("script generation completed")) continue;
      const parsed = parseMetricsFromLogDetails(log.details);
      if (parsed) return parsed;
    }

    return null;
  }, [logs, scriptMeta.metrics]);

  const generateDisabled =
    isLoading ||
    panels.length === 0 ||
    !config.apiBaseUrl;

  const handleSaveBenchmark = () => {
    if (!availableMetrics || timeline.length === 0) return;
    const record = createBenchmarkRecord({
      mangaName: scriptContext.mangaName,
      timeline,
      storyMemories,
      metrics: availableMetrics,
    });
    addBenchmarkRecord(record);
    setCurrentStep("benchmark");
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="bg-gradient-to-r from-white to-white/70 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
            Kịch Bản Recap
          </h2>
          <p className="text-white/70">Frontend uploads panels to backend, and backend Gemini generates understanding plus narration.</p>
        </div>
        <div className="flex gap-3">
          {timeline.length > 0 && (
            <>
              {availableMetrics && (
                <Button
                  variant="outline"
                  onClick={handleSaveBenchmark}
                  disabled={isLoading}
                  className="border-emerald-500/30 bg-emerald-500/10 px-6 font-bold text-emerald-100 hover:bg-emerald-500/15"
                >
                  <Save className="mr-2 h-4 w-4" /> Save benchmark
                </Button>
              )}
              <Button
                variant="outline"
                onClick={clearScriptData}
                disabled={isLoading}
                className="border-red-500/30 bg-red-500/10 px-6 font-bold text-red-200 hover:bg-red-500/15"
              >
                <Trash2 className="mr-2 h-4 w-4" /> Xóa script cache
              </Button>
              <Button
                variant="outline"
                onClick={generateScript}
                disabled={generateDisabled}
                className="border-primary/30 bg-primary/10 px-6 font-bold text-primary hover:bg-primary/15"
              >
                {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                Regenerate
              </Button>
            </>
          )}
          <Button variant="outline" onClick={() => setCurrentStep(virtualStrip.length > 0 ? "extract" : "upload")} className="bg-white/5 border-white/10 text-white hover:bg-white/10 px-6 font-bold">
            <ChevronLeft className="w-4 h-4" /> Quay lại
          </Button>
          <Button onClick={() => setCurrentStep("voice")} disabled={timeline.length === 0} className="group px-8 font-bold">
            Tiếp tục <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="glass space-y-6 rounded-3xl border-white/10 bg-white/5 p-8 shadow-2xl">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Pipeline</p>
              <p className="mt-2 text-sm font-bold text-white">Backend Gemini</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Backend URL</p>
              <p className="mt-2 truncate text-sm font-bold text-white">{config.apiBaseUrl || "Missing"}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mangaName" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">Tên truyện (tùy chọn)</Label>
              <Input id="mangaName" value={scriptContext.mangaName ?? ""} onChange={(e) => setScriptContext({ mangaName: e.target.value })} className="h-12 rounded-xl border-white/20 bg-white/10 text-white" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mainChar" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">Tên nhân vật gợi ý (tùy chọn)</Label>
              <Input id="mainChar" value={scriptContext.mainCharacter ?? ""} onChange={(e) => setScriptContext({ mainCharacter: e.target.value })} className="h-12 rounded-xl border-white/20 bg-white/10 text-white" />
              <p className="text-xs leading-5 text-white/45">Backend chỉ dùng tên này khi hình ảnh hoặc hội thoại xác nhận rõ. Nếu cảnh mơ hồ, hệ thống sẽ quay về cách gọi trung tính.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="summary" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">Bối cảnh tóm tắt</Label>
              <Textarea id="summary" value={scriptContext.summary ?? ""} onChange={(e) => setScriptContext({ summary: e.target.value })} className="min-h-[120px] rounded-xl border-white/20 bg-white/10 text-white" />
            </div>
          </div>

          <Button
            size="lg"
            onClick={generateScript}
            disabled={generateDisabled}
            className="group btn-pop h-16 w-full rounded-2xl border-none bg-primary text-xl font-black uppercase tracking-tighter text-primary-foreground ring-2 ring-white/10 shadow-glow transition-all hover:opacity-100 active:scale-[0.98]"
          >
            {isGenerating ? <Loader2 className="mr-2 h-5 w-5 animate-spin text-white" /> : <Wand2 className="mr-2 h-5 w-5" />}
            {isGenerating ? "Đang chạy backend Gemini..." : "Tự động viết kịch bản"}
          </Button>

          {(error || latestErrorDetails) && (
            <div className="space-y-2 rounded-2xl border border-red-500/30 bg-red-500/10 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-red-100">
                <AlertCircle className="h-4 w-4" /> Generation error
              </div>
              {error && <p className="text-sm text-red-100/90">{error}</p>}
              {latestErrorDetails && <pre className="whitespace-pre-wrap rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-red-50/80">{latestErrorDetails}</pre>}
            </div>
          )}
        </Card>

        <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
          <ScriptLogs />
        </Card>
      </div>

      {timeline.length > 0 && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 2xl:grid-cols-3">
          {timeline.map((item, index) => {
            const panel = panelById.get(item.panelId);
            return (
              <Card key={item.panelId} className="glass group overflow-hidden rounded-3xl border-white/10 bg-white/5 p-5 transition-all duration-300 hover:bg-white/10 hover:border-white/20">
                <div className="flex flex-col gap-5">
                  <div className="flex items-center gap-4">
                    <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary text-2xl font-black text-primary-foreground">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <div className="space-y-0.5">
                      <p className="text-lg font-bold text-white">Cảnh {index + 1}</p>
                    </div>
                  </div>

                  <div className="relative aspect-[16/10] w-full overflow-hidden rounded-2xl border border-white/10 bg-black/40">
                      {panel && (
                        <button 
                          className="h-full w-full overflow-hidden" 
                          onClick={() => setZoomedIdx(index)}
                        >
                        <img 
                          src={panel.base64 || panel.thumbnail} 
                          alt={`Panel ${index + 1}`} 
                          className="h-full w-full object-contain transition-transform duration-700 hover:scale-110" 
                        />
                      </button>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label className="text-[10px] font-bold uppercase tracking-widest text-white/40">Nội dung thuyết minh</Label>
                    <Textarea
                      value={item.scriptItem.voiceover_text || ""}
                      onChange={(e) => updateTimelineItem(index, { scriptItem: { ...item.scriptItem, voiceover_text: e.target.value } })}
                      className="min-h-[140px] resize-none rounded-xl border-white/10 bg-black/30 p-4 text-sm font-medium leading-relaxed text-white focus:ring-primary/50"
                    />
                  </div>
                </div>
              </Card>
            );
          })}

          {panelUnderstandings.length > 0 && (
            <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-white/80">Panel Understanding</h3>
                  <p className="text-xs text-white/45">Generated by backend Gemini stage 1.</p>
                </div>
                {panelUnderstandingMeta.generatedAt && <span className="text-[10px] uppercase tracking-wider text-white/55">{new Date(panelUnderstandingMeta.generatedAt).toLocaleString()}</span>}
              </div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {panelUnderstandings.map((item) => (
                  <div key={item.panelId} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="text-sm font-medium leading-relaxed text-white/90">{item.summary || "Chưa có tóm tắt."}</p>
                    <p className="mt-3 text-xs text-white/60">Action: {item.action || "--"}</p>
                    <p className="mt-1 text-xs text-white/60">Dialogue: {item.dialogue || "--"}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {zoomedIdx !== null && (
        (() => {
          const item = timeline[zoomedIdx];
          if (!item) return null;
          const panel = panelById.get(item.panelId);
          const imageSrc = panel?.base64 || panel?.thumbnail;
          if (!imageSrc) return null;

          return createPortal(
            <div 
              className="fixed inset-0 z-[200] flex items-center justify-center p-4 md:p-8" 
              onClick={() => setZoomedIdx(null)}
            >
              <div className="absolute inset-0 bg-black/95 backdrop-blur-2xl animate-in fade-in duration-500" />
              
              <button 
                className="absolute left-6 z-30 flex h-20 w-14 items-center justify-center rounded-2xl bg-white/5 text-white/40 backdrop-blur-md transition-all hover:bg-white/10 hover:text-white hover:scale-105 active:scale-95"
                onClick={(e) => { e.stopPropagation(); navigateZoom(-1); }}
              >
                <ChevronLeft className="h-10 w-10" />
              </button>

              <div 
                className="relative z-10 flex max-h-full max-w-full flex-col items-center animate-in zoom-in-95 duration-500 ease-out"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="group relative overflow-hidden rounded-2xl border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.8)]">
                  <img 
                    src={imageSrc} 
                    alt={`Zoomed panel ${zoomedIdx + 1}`} 
                    className="max-h-[85vh] w-auto max-w-full object-contain" 
                  />
                  <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-4 py-1.5 text-xs font-bold text-white/80 backdrop-blur-md border border-white/10">
                    Cảnh {zoomedIdx + 1} / {timeline.length}
                  </div>
                </div>
                
                <button 
                  className="mt-6 flex h-14 w-14 items-center justify-center rounded-full bg-white/10 text-white/50 backdrop-blur-md transition-all hover:bg-red-500/20 hover:text-red-400 hover:scale-110 active:scale-95" 
                  onClick={() => setZoomedIdx(null)}
                >
                  <X className="h-8 w-8" />
                </button>
              </div>

              <button 
                className="absolute right-6 z-30 flex h-20 w-14 items-center justify-center rounded-2xl bg-white/5 text-white/40 backdrop-blur-md transition-all hover:bg-white/10 hover:text-white hover:scale-105 active:scale-95"
                onClick={(e) => { e.stopPropagation(); navigateZoom(1); }}
              >
                <ChevronRight className="h-10 w-10" />
              </button>
            </div>,
            document.body
          );
        })()
      )}
    </div>
  );
}
