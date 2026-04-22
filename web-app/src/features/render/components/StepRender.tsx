import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  ChevronLeft,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Sparkles,
  Video,
  Volume2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useVoiceGeneration } from "@/features/voice/hooks/useVoiceGeneration";
import { renderPlanToMp4, type RenderProgressUpdate } from "@/features/render/lib/renderEngine";
import { buildRenderPlan, validateRenderPlan } from "@/features/render/lib/renderPlan";
import { useRecapStore } from "@/shared/storage/useRecapStore";

const formatSeconds = (milliseconds: number): string => `${(milliseconds / 1000).toFixed(1)}s`;

export function StepRender() {
  const {
    timeline,
    panels,
    renderConfig,
    setRenderConfig,
    updateTimelineItem,
    moveTimelineItem,
    setCurrentStep,
  } = useRecapStore();
  const { generateSingleVoice, error: voiceError } = useVoiceGeneration();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [activeTab, setActiveTab] = useState("timeline");
  const [playingIndex, setPlayingIndex] = useState<number | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState<RenderProgressUpdate | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const validationErrors = useMemo(
    () => validateRenderPlan(timeline, panels),
    [panels, timeline]
  );

  const renderPlan = useMemo(() => {
    if (validationErrors.length > 0) return null;
    return buildRenderPlan(timeline, panels, renderConfig);
  }, [panels, renderConfig, timeline, validationErrors]);

  const activeClipCount = useMemo(
    () => timeline.filter((item) => item.enabled !== false).length,
    [timeline]
  );

  const totalDurationMs = renderPlan?.totalDurationMs ?? 0;

  const togglePlayAudio = (index: number, url?: string) => {
    if (!url || !audioRef.current) return;
    if (playingIndex === index) {
      audioRef.current.pause();
      setPlayingIndex(null);
      return;
    }

    audioRef.current.src = url;
    void audioRef.current.play();
    setPlayingIndex(index);
    audioRef.current.onended = () => setPlayingIndex(null);
  };

  const handleRender = async () => {
    if (!renderPlan) return;

    setIsRendering(true);
    setRenderError(null);

    try {
      const nextBlob = await renderPlanToMp4(renderPlan, setRenderProgress);
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      setPreviewUrl(URL.createObjectURL(nextBlob));
      setActiveTab("export");
    } catch (error) {
      setRenderError(error instanceof Error ? error.message : "Render failed.");
    } finally {
      setIsRendering(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <audio ref={audioRef} className="hidden" />

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
            Timeline & Render
          </h2>
          <p className="text-sm text-white/65">
            M4 timeline editor and M5 browser export share one active source of truth.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => setCurrentStep("voice")}
            className="border-white/10 bg-white/5 px-6 font-bold text-white hover:bg-white/10"
          >
            <ChevronLeft className="h-4 w-4" /> Back
          </Button>
          <Button
            onClick={handleRender}
            disabled={isRendering || !!validationErrors.length}
            className="px-8 font-bold"
          >
            {isRendering ? <Loader2 className="h-4 w-4 animate-spin" /> : <Video className="h-4 w-4" />}
            Render MP4
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="glass rounded-3xl border-white/10 bg-white/5 p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Active Clips</p>
          <p className="mt-2 text-2xl font-bold text-white">{activeClipCount}</p>
        </Card>
        <Card className="glass rounded-3xl border-white/10 bg-white/5 p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Total Duration</p>
          <p className="mt-2 text-2xl font-bold text-white">{formatSeconds(totalDurationMs)}</p>
        </Card>
        <Card className="glass rounded-3xl border-white/10 bg-white/5 p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Render Output</p>
          <p className="mt-2 text-2xl font-bold text-white">
            {renderConfig.outputWidth} x {Math.round(renderConfig.outputWidth / renderConfig.aspectRatio)}
          </p>
        </Card>
      </div>

      {(validationErrors.length > 0 || renderError || voiceError) && (
        <Card className="rounded-3xl border border-red-500/25 bg-red-500/10 p-5 text-red-50">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <AlertCircle className="h-4 w-4" /> Blocking Issues
          </div>
          <div className="mt-3 space-y-2 text-sm text-red-100/90">
            {validationErrors.map((error) => (
              <p key={error}>{error}</p>
            ))}
            {renderError && <p>{renderError}</p>}
            {voiceError && <p>{voiceError}</p>}
          </div>
        </Card>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="rounded-2xl border border-white/10 bg-white/5 p-1.5">
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="export">Export</TabsTrigger>
        </TabsList>

        <TabsContent value="timeline" className="space-y-4 pt-4">
          {timeline.map((item, index) => {
            const panel = panels.find((entry) => entry.id === item.panelId);
            const isPlaying = playingIndex === index;
            const isEnabled = item.enabled !== false;

            return (
              <Card
                key={item.panelId}
                className={`glass rounded-3xl border p-5 transition-colors ${
                  isEnabled ? "border-white/10 bg-white/5" : "border-white/5 bg-black/20 opacity-70"
                }`}
              >
                <div className="flex flex-col gap-5 xl:flex-row">
                  <div className="flex items-start gap-4 xl:w-[220px]">
                    <div className="h-28 w-24 overflow-hidden rounded-2xl border border-white/10 bg-black/40">
                      {panel ? (
                        <img src={panel.thumbnail} alt={`Panel ${index + 1}`} className="h-full w-full object-cover" />
                      ) : null}
                    </div>
                    <div className="space-y-2">
                      <p className="text-lg font-bold text-white">Clip {index + 1}</p>
                      <div className="flex flex-wrap gap-2 text-xs text-white/60">
                        <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1">
                          {item.audioStatus || "missing"}
                        </span>
                        <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1">
                          {formatSeconds(
                            item.audioStatus === "ready" && typeof item.audioDuration === "number"
                              ? Math.round(item.audioDuration * 1000) + (item.holdAfterMs ?? 250)
                              : Math.max(1500, item.holdAfterMs ?? 250)
                          )}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex-1 space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        variant={isEnabled ? "secondary" : "outline"}
                        size="sm"
                        onClick={() => updateTimelineItem(index, { enabled: !isEnabled })}
                        className="rounded-xl"
                      >
                        {isEnabled ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                        {isEnabled ? "Active" : "Disabled"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => moveTimelineItem(index, index - 1)}
                        disabled={index === 0}
                        className="rounded-xl"
                      >
                        <ArrowUp className="h-4 w-4" /> Move up
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => moveTimelineItem(index, index + 1)}
                        disabled={index === timeline.length - 1}
                        className="rounded-xl"
                      >
                        <ArrowDown className="h-4 w-4" /> Move down
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => generateSingleVoice(index)}
                        className="rounded-xl"
                      >
                        <RefreshCw className="h-4 w-4" /> Regenerate audio
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => togglePlayAudio(index, item.audioUrl)}
                        disabled={!item.audioUrl || item.audioStatus !== "ready"}
                        className="rounded-xl"
                      >
                        {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                        {isPlaying ? "Stop" : "Preview"}
                      </Button>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-[1fr_180px]">
                      <div className="space-y-2">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                          Narration
                        </p>
                        <Textarea
                          value={item.scriptItem.voiceover_text}
                          onChange={(event) =>
                            updateTimelineItem(index, {
                              scriptItem: {
                                ...item.scriptItem,
                                voiceover_text: event.target.value,
                              },
                            })
                          }
                          className="min-h-[132px] rounded-2xl border-white/10 bg-black/25 text-white"
                        />
                      </div>

                      <div className="space-y-4">
                        <div className="space-y-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                            Hold After (ms)
                          </p>
                          <Input
                            type="number"
                            min="0"
                            max="3000"
                            step="50"
                            value={item.holdAfterMs ?? 250}
                            onChange={(event) =>
                              updateTimelineItem(index, {
                                holdAfterMs: Number(event.target.value) || 0,
                              })
                            }
                            className="rounded-2xl border-white/10 bg-black/25 text-white"
                          />
                        </div>

                        <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/60">
                          Active clip duration resolves from ready audio + hold, or falls back to a silent minimum clip.
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </TabsContent>

        <TabsContent value="export" className="space-y-4 pt-4">
          <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
            <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="space-y-5">
                <div className="space-y-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                    Caption Burn-In
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant={renderConfig.captionMode === "off" ? "secondary" : "outline"}
                      onClick={() => setRenderConfig({ captionMode: "off" })}
                      className="rounded-xl"
                    >
                      Off
                    </Button>
                    <Button
                      variant={renderConfig.captionMode === "burned" ? "secondary" : "outline"}
                      onClick={() => setRenderConfig({ captionMode: "burned" })}
                      className="rounded-xl"
                    >
                      Burned
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                    Export Action
                  </p>
                  <Button
                    size="lg"
                    onClick={handleRender}
                    disabled={isRendering || !!validationErrors.length}
                    className="h-14 w-full rounded-2xl text-lg font-bold"
                  >
                    {isRendering ? <Loader2 className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}
                    Export MP4
                  </Button>
                </div>

                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/65">
                  Output uses browser-only FFmpeg with static frames, hard cuts, backend-generated WAV clips, and optional caption burn-in.
                </div>

                {renderProgress && (
                  <div className="rounded-2xl border border-primary/20 bg-primary/10 p-4 text-sm text-primary-foreground">
                    <p className="font-semibold text-white">{renderProgress.phase}</p>
                    <p className="mt-1 text-white/70">{renderProgress.detail || "Working..."}</p>
                    <p className="mt-2 text-xs uppercase tracking-[0.2em] text-white/55">
                      {renderProgress.progress}%
                    </p>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                {previewUrl ? (
                  <Card className="rounded-3xl border border-white/10 bg-black/25 p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                      <Volume2 className="h-4 w-4" /> Preview
                    </div>
                    <video src={previewUrl} controls className="w-full rounded-2xl border border-white/10 bg-black" />
                  </Card>
                ) : (
                  <Card className="flex min-h-[320px] items-center justify-center rounded-3xl border border-dashed border-white/10 bg-black/20 p-6 text-center text-white/55">
                    Rendered MP4 preview will appear here.
                  </Card>
                )}
              </div>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
