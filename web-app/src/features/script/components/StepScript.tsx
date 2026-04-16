import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Eye,
  Loader2,
  RefreshCw,
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
import { useRecapStore } from "@/shared/storage/useRecapStore";

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
    setCurrentStep,
    clearScriptData,
    isLoading,
  } = useRecapStore();
  const { generateScript, error, isGenerating } = useScriptJob();
  const [zoomedImage, setZoomedImage] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showRawScript, setShowRawScript] = useState(false);
  const [showRawUnderstanding, setShowRawUnderstanding] = useState(false);
  const [showMemories, setShowMemories] = useState(false);

  const panelById = useMemo(() => new Map(panels.map((panel) => [panel.id, panel])), [panels]);
  const latestErrorDetails = useMemo(() => {
    for (let index = logs.length - 1; index >= 0; index -= 1) {
      const log = logs[index];
      if (log.type === "error" && log.details) return log.details;
    }
    return null;
  }, [logs]);

  const generateDisabled =
    isLoading ||
    panels.length === 0 ||
    !scriptContext.mangaName ||
    !scriptContext.mainCharacter ||
    !config.apiBaseUrl;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="bg-gradient-to-r from-white to-white/70 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
            Kich Ban Recap
          </h2>
          <p className="text-white/70">Frontend uploads panels to backend, and backend Gemini generates understanding plus narration.</p>
        </div>
        <div className="flex gap-3">
          {timeline.length > 0 && (
            <>
              <Button
                variant="outline"
                onClick={clearScriptData}
                disabled={isLoading}
                className="rounded-xl border-red-500/30 bg-red-500/10 px-6 font-bold text-red-200 hover:bg-red-500/15"
              >
                <Trash2 className="mr-2 h-4 w-4" /> Xoa script cache
              </Button>
              <Button
                variant="outline"
                onClick={generateScript}
                disabled={generateDisabled}
                className="rounded-xl border-primary/30 bg-primary/10 px-6 font-bold text-primary hover:bg-primary/15"
              >
                {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                Regenerate
              </Button>
            </>
          )}
          <Button variant="outline" onClick={() => setCurrentStep(virtualStrip.length > 0 ? "extract" : "upload")} className="rounded-xl border-white/30 bg-white/10 px-6 font-bold text-white hover:bg-white/20">
            <ChevronLeft className="mr-2 h-4 w-4" /> Quay lai
          </Button>
          <Button onClick={() => setCurrentStep("voice")} disabled={timeline.length === 0} className="rounded-xl bg-primary px-8 font-black uppercase tracking-tight text-primary-foreground">
            Tiep tuc <ChevronRight className="ml-2 h-4 w-4" />
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
              <Label htmlFor="mangaName" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">Ten truyen</Label>
              <Input id="mangaName" value={scriptContext.mangaName} onChange={(e) => setScriptContext({ mangaName: e.target.value })} className="h-12 rounded-xl border-white/20 bg-white/10 text-white" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mainChar" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">Nhan vat chinh</Label>
              <Input id="mainChar" value={scriptContext.mainCharacter} onChange={(e) => setScriptContext({ mainCharacter: e.target.value })} className="h-12 rounded-xl border-white/20 bg-white/10 text-white" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="summary" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">Boi canh tom tat</Label>
              <Textarea id="summary" value={scriptContext.summary} onChange={(e) => setScriptContext({ summary: e.target.value })} className="min-h-[120px] rounded-xl border-white/20 bg-white/10 text-white" />
            </div>
          </div>

          <Button
            size="lg"
            onClick={generateScript}
            disabled={generateDisabled}
            className="group h-16 w-full rounded-2xl border-none bg-primary text-xl font-black uppercase tracking-tighter text-primary-foreground ring-2 ring-white/10"
          >
            {isGenerating ? <Loader2 className="mr-2 h-5 w-5 animate-spin text-white" /> : <Wand2 className="mr-2 h-5 w-5" />}
            {isGenerating ? "Dang chay backend Gemini..." : "Tu dong viet kich ban"}
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
        <div className="space-y-6">
          {timeline.map((item, index) => {
            const panel = panelById.get(item.panelId);
            return (
              <Card key={item.panelId} className="glass rounded-3xl border-white/10 bg-white/5 p-6">
                <div className="flex flex-col gap-6 xl:flex-row">
                  <div className="relative w-full shrink-0 xl:w-72">
                    {panel && (
                      <button className="w-full overflow-hidden rounded-2xl border border-white/10 bg-black/30 shadow-xl" onClick={() => setZoomedImage(panel.thumbnail)}>
                        <img src={panel.thumbnail} alt={`Panel ${index + 1}`} className="aspect-[9/16] w-full object-cover" />
                      </button>
                    )}
                  </div>
                  <div className="flex-1 space-y-4">
                    <div className="flex items-center gap-2">
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-white ring-1 ring-primary/50">{index + 1}</span>
                      <h4 className="text-[10px] font-extrabold uppercase tracking-wider text-white/90">Canh #{index + 1}</h4>
                    </div>
                    <Textarea
                      value={item.scriptItem.voiceover_text || ""}
                      onChange={(e) => updateTimelineItem(index, { scriptItem: { ...item.scriptItem, voiceover_text: e.target.value } })}
                      className="min-h-[120px] resize-y rounded-2xl border-primary/20 bg-primary/10 p-4 text-base font-medium leading-relaxed text-white"
                    />
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white/80">
                      <span className="mr-2 text-[10px] font-extrabold uppercase tracking-wider text-primary">AI View</span>
                      {item.scriptItem.ai_view}
                    </div>
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
                    <p className="text-sm font-medium leading-relaxed text-white/90">{item.summary || "Chua co tom tat."}</p>
                    <p className="mt-3 text-xs text-white/60">Action: {item.action || "--"}</p>
                    <p className="mt-1 text-xs text-white/60">Dialogue: {item.dialogue || "--"}</p>
                    <p className="mt-1 text-xs text-white/60">SFX: {(item.sfx || []).join(", ") || "--"}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {(scriptMeta.rawOutput || panelUnderstandingMeta.rawOutput) && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {scriptMeta.rawOutput && (
                <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
                  <div className="mb-3 flex items-center justify-between">
                    <button className="text-left" onClick={() => setShowRawScript(!showRawScript)}>
                      <h3 className="text-sm font-bold uppercase tracking-wider text-white/80">Raw Narration Output</h3>
                    </button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg bg-white/5 text-white/50 hover:bg-white/10 hover:text-white" onClick={() => { void navigator.clipboard.writeText(scriptMeta.rawOutput || ""); setCopiedId("script"); window.setTimeout(() => setCopiedId(null), 2000); }}>
                      {copiedId === "script" ? <Eye className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                  {showRawScript && <Textarea value={scriptMeta.rawOutput} readOnly className="min-h-[220px] rounded-2xl border-white/10 bg-black/30 font-mono text-xs leading-6 text-white/75" />}
                </Card>
              )}
              {panelUnderstandingMeta.rawOutput && (
                <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
                  <div className="mb-3 flex items-center justify-between">
                    <button className="text-left" onClick={() => setShowRawUnderstanding(!showRawUnderstanding)}>
                      <h3 className="text-sm font-bold uppercase tracking-wider text-white/80">Raw Understanding Output</h3>
                    </button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg bg-white/5 text-white/50 hover:bg-white/10 hover:text-white" onClick={() => { void navigator.clipboard.writeText(panelUnderstandingMeta.rawOutput || ""); setCopiedId("understanding"); window.setTimeout(() => setCopiedId(null), 2000); }}>
                      {copiedId === "understanding" ? <Eye className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                  {showRawUnderstanding && <Textarea value={panelUnderstandingMeta.rawOutput} readOnly className="min-h-[220px] rounded-2xl border-white/10 bg-black/30 font-mono text-xs leading-6 text-white/75" />}
                </Card>
              )}
            </div>
          )}

          {storyMemories.length > 0 && (
            <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
              <div className="mb-3 flex items-center justify-between">
                <button className="text-left" onClick={() => setShowMemories(!showMemories)}>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-white/80">Story Memory</h3>
                </button>
                <ChevronDown className={`h-4 w-4 text-white/50 transition-transform ${showMemories ? "" : "-rotate-90"}`} />
              </div>
              {showMemories && (
                <div className="space-y-3">
                  {storyMemories.map((memory) => (
                    <div key={memory.chunkIndex} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                      <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-white/60">Chunk {memory.chunkIndex + 1}</p>
                      <p className="text-sm leading-6 text-white/85">{memory.summary}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {zoomedImage &&
        createPortal(
          <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/90 p-4 backdrop-blur-md" onClick={() => setZoomedImage(null)}>
            <img src={zoomedImage} alt="Zoomed detail" className="max-h-full max-w-full rounded-2xl shadow-2xl" onClick={(e) => e.stopPropagation()} />
            <button className="absolute right-6 top-6 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white/50 hover:bg-white/20 hover:text-white" onClick={() => setZoomedImage(null)}>
              <X className="h-6 w-6" />
            </button>
          </div>,
          document.body
        )}
    </div>
  );
}
