import { useMemo, useState } from "react";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Eye,
  Ghost,
  History,
  Loader2,
  Mic,
  Music,
  RefreshCw,
  Trash2,
  Wand2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { ScriptLogs } from "@/features/script/components/ScriptLogs";
import { useScriptJob } from "@/features/script/hooks/useScriptJob";
import { useRecapStore } from "@/shared/storage/useRecapStore";

export function StepScript() {
  const {
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
    setTimeline,
    setScriptMeta,
    clearScriptData,
    setCurrentStep,
    isLoading,
    scriptJob,
  } = useRecapStore();
  const { generateScript, cancelActiveScriptJob, error, isGenerating } = useScriptJob();
  const [replacementName, setReplacementName] = useState("");

  const nextStep = () => setCurrentStep("voice");
  const prevStep = () => setCurrentStep(virtualStrip.length > 0 ? "extract" : "upload");

  const unknownCharacters = useMemo(() => {
    const found = new Set<string>();
    timeline.forEach((item) => {
      const voiceMatch = item.scriptItem.voiceover_text?.match(/\[(.*?)\]/g);
      voiceMatch?.forEach((match) => found.add(match));
    });
    return Array.from(found);
  }, [timeline]);

  const editedCount = useMemo(
    () => timeline.filter((item) => item.scriptStatus === "edited").length,
    [timeline]
  );

  const latestErrorDetails = useMemo(() => {
    for (let index = logs.length - 1; index >= 0; index -= 1) {
      const log = logs[index];
      if (log.type === "error" && log.details) {
        return log.details;
      }
    }
    return null;
  }, [logs]);

  const handleReplaceCharacter = (placeholder: string) => {
    if (!replacementName) return;

    const escaped = placeholder.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const newTimeline = timeline.map((item) => ({
      ...item,
      scriptItem: {
        ...item.scriptItem,
        voiceover_text:
          item.scriptItem.voiceover_text?.replace(new RegExp(escaped, "g"), replacementName) || "",
      },
      scriptStatus: "edited" as const,
      scriptSegment: {
        narration:
          item.scriptItem.voiceover_text?.replace(new RegExp(escaped, "g"), replacementName) || "",
        status: "edited" as const,
      },
    }));

    setTimeline(newTimeline);
    setScriptMeta({
      ...scriptMeta,
      status: "edited",
      outdatedReason: undefined,
    });
    setReplacementName("");
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="bg-gradient-to-r from-white to-white/70 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
            Kich ban Recap
          </h2>
          <p className="text-white/70">
            AI backend viet kich ban dua tren panel da extract. Co the chinh sua thu cong.
          </p>
          {timeline.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px] uppercase tracking-wider">
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-white/70">
                Status: {scriptMeta.status}
              </span>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-white/70">
                Edited: {editedCount}/{timeline.length}
              </span>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-white/70">
                Pipeline: {scriptMeta.pipeline ?? "backend-caption-memory"}
              </span>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-white/70">
                Job: {scriptJob.status}
              </span>
            </div>
          )}
        </div>
        <div className="flex gap-3">
          {timeline.length > 0 && (
            <Button
              variant="outline"
              onClick={clearScriptData}
              disabled={isLoading}
              className="rounded-xl border-red-500/30 bg-red-500/10 px-6 font-bold text-red-200 transition-all hover:bg-red-500/15"
            >
              <Trash2 className="mr-2 h-4 w-4" /> Xoa script cache
            </Button>
          )}
          {timeline.length > 0 && (
            <Button
              variant="outline"
              onClick={generateScript}
              disabled={isLoading || panels.length === 0 || !scriptContext.mangaName || !scriptContext.mainCharacter}
              className="rounded-xl border-primary/30 bg-primary/10 px-6 font-bold text-primary transition-all hover:bg-primary/15"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Dang tao lai
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" /> Regenerate
                </>
              )}
            </Button>
          )}
          {(scriptJob.status === "queued" || scriptJob.status === "running") && (
            <Button
              variant="outline"
              onClick={cancelActiveScriptJob}
              className="rounded-xl border-amber-500/30 bg-amber-500/10 px-6 font-bold text-amber-100 transition-all hover:bg-amber-500/15"
            >
              Huy job backend
            </Button>
          )}
          <Button
            variant="outline"
            onClick={prevStep}
            className="rounded-xl border-white/30 bg-white/10 px-6 font-bold text-white shadow-sm ring-1 ring-white/10 transition-all hover:bg-white/20"
          >
            <ChevronLeft className="mr-2 h-4 w-4" /> Quay lai
          </Button>
          <Button
            onClick={nextStep}
            disabled={timeline.length === 0}
            className="rounded-xl bg-primary px-8 font-black uppercase tracking-tight text-primary-foreground shadow-glow shadow-glow-hover transition-all"
          >
            Tiep tuc <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>

      {timeline.length === 0 ? (
        <div className="grid h-full grid-cols-1 gap-8 lg:grid-cols-2">
          <Card className="glass space-y-6 rounded-3xl border-white/10 bg-white/5 p-8 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-primary/30 p-2 ring-1 ring-primary/50">
                <History className="h-5 w-5 text-white" />
              </div>
              <h3 className="text-xl font-bold text-white">Thiet lap boi canh</h3>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="mangaName" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">
                  Ten truyen
                </Label>
                <Input
                  id="mangaName"
                  placeholder="VD: Cau Ma, Vo Luyen Dinh Phong..."
                  value={scriptContext.mangaName}
                  onChange={(e) => setScriptContext({ mangaName: e.target.value })}
                  className="h-12 rounded-xl border-white/20 bg-white/10 text-white placeholder:text-white/30 focus:border-primary/50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="mainChar" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">
                  Nhan vat chinh
                </Label>
                <Input
                  id="mainChar"
                  placeholder="VD: To Minh, Duong Khai..."
                  value={scriptContext.mainCharacter}
                  onChange={(e) => setScriptContext({ mainCharacter: e.target.value })}
                  className="h-12 rounded-xl border-white/20 bg-white/10 text-white placeholder:text-white/30 focus:border-primary/50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="summary" className="text-[10px] font-semibold uppercase tracking-wide text-white/80">
                  Boi canh tom tat (Tuy chon)
                </Label>
                <Textarea
                  id="summary"
                  placeholder="VD: Sau khi dot pha canh gioi, To Minh dang tim cach tra thu..."
                  value={scriptContext.summary}
                  onChange={(e) => setScriptContext({ summary: e.target.value })}
                  className="min-h-[120px] rounded-xl border-white/20 bg-white/10 text-white placeholder:text-white/30 focus:border-primary/50"
                />
              </div>
            </div>

            <Button
              size="lg"
              onClick={generateScript}
              disabled={isLoading || panels.length === 0 || !scriptContext.mangaName || !scriptContext.mainCharacter}
              className="group mt-4 h-16 w-full rounded-2xl border-none bg-primary text-xl font-black uppercase tracking-tighter text-primary-foreground shadow-glow shadow-glow-hover ring-2 ring-white/10 transition-all active:scale-[0.98]"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin text-white" />
                  Dang chay backend...
                </>
              ) : (
                <>
                  Tu dong viet kich ban
                  <Wand2 className="ml-2 h-5 w-5 transition-transform group-hover:rotate-12" />
                </>
              )}
            </Button>

            {(scriptJob.status === "queued" || scriptJob.status === "running") && (
              <Button
                variant="outline"
                onClick={cancelActiveScriptJob}
                className="rounded-xl border-amber-500/30 bg-amber-500/10 px-6 font-bold text-amber-100 transition-all hover:bg-amber-500/15"
              >
                Huy job backend
              </Button>
            )}

            {error && (
              <div className="space-y-3 rounded-xl border border-destructive/30 bg-destructive/20 p-4 text-sm text-white shadow-inner">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 text-[#ff4d4d]" />
                  <span>{error}</span>
                </div>
                {latestErrorDetails && (
                  <pre className="overflow-x-auto rounded-lg border border-white/10 bg-black/30 p-3 font-mono text-[10px] leading-5 text-white/85">
                    <code>{latestErrorDetails}</code>
                  </pre>
                )}
              </div>
            )}
          </Card>

          <Card className="glass flex flex-col rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl">
            <ScriptLogs />
          </Card>
        </div>
      ) : (
        <div className="space-y-6 pb-20">
          {scriptMeta.status === "outdated" && (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              Script hien tai khong con khop hoan toan voi panel extract hien tai.
              {scriptMeta.outdatedReason ? ` ${scriptMeta.outdatedReason}` : ""}
            </div>
          )}

          {unknownCharacters.length > 0 && (
            <div className="ring-primary/20 animate-in slide-in-from-top-4 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-primary/50 bg-primary/30 p-4 shadow-lg ring-1">
              <div className="flex items-center gap-3">
                <Ghost className="h-5 w-5 text-white" />
                <p className="text-sm font-bold text-white">
                  Phat hien nhan vat vo danh:
                  <span className="ml-2 rounded-lg bg-primary/40 px-2 py-0.5 font-bold text-white">
                    {unknownCharacters[0]}
                  </span>
                </p>
              </div>
              <div className="flex max-w-md flex-1 gap-2">
                <Input
                  placeholder="Nhap ten that..."
                  value={replacementName}
                  onChange={(e) => setReplacementName(e.target.value)}
                  className="h-9 border-white/20 bg-black/40 text-white placeholder:text-white/30"
                  onKeyDown={(e) => e.key === "Enter" && handleReplaceCharacter(unknownCharacters[0])}
                />
                <Button
                  size="sm"
                  onClick={() => handleReplaceCharacter(unknownCharacters[0])}
                  className="shrink-0 rounded-lg bg-primary px-4 font-bold text-primary-foreground shadow-glow shadow-glow-hover hover:opacity-90"
                >
                  Thay the
                </Button>
              </div>
            </div>
          )}

          <ScrollArea className="glass h-[calc(100vh-220px)] rounded-3xl border border-white/10 bg-white/5 p-2">
            <div className="space-y-4 p-4">
              {timeline.map((item, index) => {
                const panel = panels.find((candidate) => candidate.id === item.panelId);
                return (
                  <Card
                    key={item.panelId}
                    className="group flex flex-col gap-6 overflow-hidden rounded-3xl border-white/10 bg-white/5 p-6 shadow-lg transition-all duration-300 hover:border-primary/40 hover:bg-white/10"
                  >
                    <div className="flex flex-col gap-6 md:flex-row">
                      <div className="aspect-[3/4] w-full shrink-0 overflow-hidden rounded-2xl border border-white/10 bg-black shadow-2xl transition-colors group-hover:border-primary/40 md:w-56">
                        <img
                          src={panel?.thumbnail}
                          alt={`Panel ${index + 1}`}
                          className="h-full w-full object-contain"
                        />
                      </div>

                      <div className="flex-1 space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-white ring-1 ring-primary/50 shadow-[0_0_10px_rgba(var(--color-primary),0.3)]">
                              {index + 1}
                            </span>
                            <h4 className="text-[10px] font-extrabold uppercase tracking-wider text-white/90">
                              Canh #{index + 1}
                            </h4>
                            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-wider text-white/55">
                              {item.scriptStatus ?? "auto"}
                            </span>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <Label className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-white/60">
                            <Mic className="h-3 w-3 text-primary" /> Kich ban doc
                          </Label>
                          <Textarea
                            value={item.scriptItem.voiceover_text || ""}
                            onChange={(e) =>
                              updateTimelineItem(index, {
                                scriptItem: { ...item.scriptItem, voiceover_text: e.target.value },
                              })
                            }
                            className="min-h-[120px] resize-y rounded-2xl border-primary/20 bg-primary/10 p-4 text-base font-medium leading-relaxed text-white shadow-inner focus-visible:ring-primary"
                            placeholder="Kich ban dan truyen da bao gom loi thoai..."
                          />
                        </div>

                        <div className="flex flex-col items-start gap-4 xl:flex-row">
                          <div className="min-h-[60px] w-full flex-1 rounded-xl border border-white/10 bg-white/5 p-3 shadow-inner">
                            <p className="text-[11px] font-medium italic leading-snug text-white/80">
                              <span className="mr-1 inline-flex items-center gap-1 text-[9px] font-extrabold uppercase not-italic text-primary">
                                <Eye className="inline h-3 w-3" /> AI View:
                              </span>
                              {item.scriptItem.ai_view}
                            </p>
                          </div>

                          <div className="w-full shrink-0 space-y-2 xl:w-72">
                            <Label className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-white/60">
                              <Music className="h-3 w-3 text-primary" /> Hieu ung am thanh (SFX)
                            </Label>
                            <div className="flex min-h-[60px] flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-black/40 p-2">
                              {(item.scriptItem.sfx || []).map((sfxItem, sfxIdx) => (
                                <span
                                  key={sfxIdx}
                                  className="flex items-center gap-1 rounded-lg border border-amber-500/30 bg-amber-500/20 px-2.5 py-1 text-[11px] font-medium text-white shadow-sm"
                                >
                                  {sfxItem}
                                  <button
                                    className="ml-1 text-white/50 hover:text-white"
                                    onClick={() => {
                                      const newSfx = [...(item.scriptItem.sfx || [])];
                                      newSfx.splice(sfxIdx, 1);
                                      updateTimelineItem(index, {
                                        scriptItem: { ...item.scriptItem, sfx: newSfx },
                                      });
                                    }}
                                  >
                                    x
                                  </button>
                                </span>
                              ))}

                              <Input
                                className="h-7 w-28 rounded-lg border-dashed border-white/20 bg-transparent px-2 text-[11px] text-white placeholder:text-white/30 focus-visible:ring-1 focus-visible:ring-amber-500/50"
                                placeholder="+ Them tag"
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    const value = e.currentTarget.value.trim();
                                    if (value) {
                                      const newSfx = [...(item.scriptItem.sfx || []), value];
                                      updateTimelineItem(index, {
                                        scriptItem: { ...item.scriptItem, sfx: newSfx },
                                      });
                                      e.currentTarget.value = "";
                                    }
                                  }
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </Card>
                );
              })}

              <Card className="glass mt-8 rounded-3xl border-white/10 bg-white/5 p-6">
                <ScriptLogs />
              </Card>

              {panelUnderstandings.length > 0 && (
                <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-bold uppercase tracking-wider text-white/80">Panel Understanding</h3>
                      <p className="text-xs text-white/45">
                        Structured scene input generated from the backend caption pipeline.
                      </p>
                    </div>
                    {panelUnderstandingMeta.generatedAt && (
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-wider text-white/55">
                        {new Date(panelUnderstandingMeta.generatedAt).toLocaleString()}
                      </span>
                    )}
                  </div>

                  <div className="space-y-3">
                    {panelUnderstandings.map((item, index) => (
                      <div key={item.panelId} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                        <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-wider text-white/60">
                          <span>Panel {index + 1}</span>
                        </div>
                        <p className="text-sm leading-6 text-white/85">{item.summary || "Chua co tom tat."}</p>
                        <div className="mt-3 grid gap-2 text-xs text-white/60 md:grid-cols-2">
                          <p>
                            <span className="text-white/40">Action:</span> {item.action || "--"}
                          </p>
                          <p>
                            <span className="text-white/40">Emotion:</span> {item.emotion || "--"}
                          </p>
                          <p>
                            <span className="text-white/40">Dialogue:</span> {item.dialogue || "--"}
                          </p>
                          <p>
                            <span className="text-white/40">Cliffhanger:</span> {item.cliffhanger || "--"}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {scriptMeta.rawOutput && (
                <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-bold uppercase tracking-wider text-white/80">Raw LLM Output</h3>
                      <p className="text-xs text-white/45">Snapshot ket qua goc da luu cho lan generate gan nhat.</p>
                    </div>
                    {scriptMeta.generatedAt && (
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-wider text-white/55">
                        {new Date(scriptMeta.generatedAt).toLocaleString()}
                      </span>
                    )}
                  </div>
                  <Textarea
                    value={scriptMeta.rawOutput}
                    readOnly
                    className="min-h-[220px] rounded-2xl border-white/10 bg-black/30 font-mono text-xs leading-6 text-white/75"
                  />
                </Card>
              )}

              {panelUnderstandingMeta.rawOutput && (
                <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-bold uppercase tracking-wider text-white/80">Raw Understanding Output</h3>
                      <p className="text-xs text-white/45">Raw caption output from the backend caption pipeline.</p>
                    </div>
                  </div>
                  <Textarea
                    value={panelUnderstandingMeta.rawOutput}
                    readOnly
                    className="min-h-[220px] rounded-2xl border-white/10 bg-black/30 font-mono text-xs leading-6 text-white/75"
                  />
                </Card>
              )}

              {storyMemories.length > 0 && (
                <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
                  <div className="mb-3">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-white/80">Story Memory</h3>
                    <p className="text-xs text-white/45">Compressed chunk memory passed between backend script batches.</p>
                  </div>

                  <div className="space-y-3">
                    {storyMemories.map((memory) => (
                      <div key={memory.chunkIndex} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                        <p className="mb-2 text-[11px] uppercase tracking-wider text-white/60">
                          Chunk {memory.chunkIndex + 1}
                        </p>
                        <p className="text-sm leading-6 text-white/85">{memory.summary}</p>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}
