import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  ChevronLeft,
  Copy,
  Download,
  FolderOpen,
  Loader2,
  Pause,
  Play,
  RectangleHorizontal,
  RectangleVertical,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Trash2,
  Video,
  Volume2,
  Wand2,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  cancelRenderJob,
  createRenderJob,
  fetchRenderJobStatus,
  revealRenderResult,
  resolveRenderResultUrl,
} from "@/features/render/api/renderApi";
import type { RenderProgressUpdate } from "@/features/render/lib/renderEngine";
import { buildRenderPlan, validateRenderPlan } from "@/features/render/lib/renderPlan";
import { useVoiceGeneration } from "@/features/voice/hooks/useVoiceGeneration";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { RenderJobStatusResponse } from "@/shared/types";

const formatSeconds = (milliseconds: number): string => `${(milliseconds / 1000).toFixed(1)}s`;

const describeRenderError = (error: unknown): string => {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
};

const clampProgress = (value: number): number => Math.max(0, Math.min(100, Math.round(value)));

const titleCasePhase = (value: string): string =>
  value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const getOptionButtonClass = (isActive: boolean): string =>
  isActive
    ? "rounded-xl border-cyan-300/45 bg-cyan-400/18 text-white shadow-[0_0_0_1px_rgba(103,232,249,0.22),0_12px_30px_rgba(34,211,238,0.16)] hover:bg-cyan-400/22"
    : "rounded-xl border-white/10 bg-white/5 text-white/72 hover:border-white/15 hover:bg-white/10 hover:text-white";

type ActiveRenderMode = "backend" | null;
type OutputPreset = "vertical" | "horizontal";

const OUTPUT_PRESETS: Record<
  OutputPreset,
  {
    label: string;
    outputWidth: number;
    aspectRatio: number;
    resolutionLabel: string;
  }
> = {
  vertical: {
    label: "9:16 dọc",
    outputWidth: 1080,
    aspectRatio: 9 / 16,
    resolutionLabel: "1080 x 1920",
  },
  horizontal: {
    label: "16:9 ngang",
    outputWidth: 1920,
    aspectRatio: 16 / 9,
    resolutionLabel: "1920 x 1080",
  },
};

export function StepRender() {
  const {
    config,
    timeline,
    panels,
    renderConfig,
    setRenderConfig,
    updateTimelineItem,
    moveTimelineItem,
    removeTimelineItem,
    duplicateTimelineItem,
    resetTimelineItemToAuto,
    setCurrentStep,
  } = useRecapStore();
  const { generateSingleVoice, generateStaleVoices, error: voiceError } = useVoiceGeneration();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const backendPollInFlightRef = useRef(false);

  const [activeTab, setActiveTab] = useState("timeline");
  const [playingIndex, setPlayingIndex] = useState<number | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const [renderMode, setRenderMode] = useState<ActiveRenderMode>(null);
  const [renderProgress, setRenderProgress] = useState<RenderProgressUpdate | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<RenderJobStatusResponse | null>(null);

  const validationErrors = useMemo(() => validateRenderPlan(timeline, panels), [panels, timeline]);

  const renderPlan = useMemo(() => {
    if (validationErrors.length > 0) return null;
    return buildRenderPlan(timeline, panels, renderConfig);
  }, [panels, renderConfig, timeline, validationErrors]);

  const activeClipCount = useMemo(
    () => timeline.filter((item) => item.enabled !== false).length,
    [timeline]
  );
  const staleClipCount = useMemo(
    () => timeline.filter((item) => item.audioStatus === "stale").length,
    [timeline]
  );

  const totalDurationMs = renderPlan?.totalDurationMs ?? 0;
  const activeOutputPreset: OutputPreset =
    renderConfig.aspectRatio > 1 ? "horizontal" : "vertical";

  useEffect(() => {
    if (!activeJobId || !isRendering || renderMode !== "backend") {
      return;
    }

    let disposed = false;

    const pollStatus = async () => {
      if (backendPollInFlightRef.current) return;
      backendPollInFlightRef.current = true;
      try {
        const status = await fetchRenderJobStatus(config.apiBaseUrl, activeJobId);
        if (disposed) return;

        setBackendStatus(status);
        setRenderProgress({
          phase: status.phase,
          progress: status.progress,
          detail: status.detail || undefined,
        });

        if (status.status === "completed") {
          setIsRendering(false);
          setActiveJobId(null);
          setActiveTab("export");
          setPreviewUrl(resolveRenderResultUrl(config.apiBaseUrl, status.downloadUrl));
          setRenderError(null);
          return;
        }

        if (status.status === "failed" || status.status === "cancelled") {
          setIsRendering(false);
          setActiveJobId(null);
          const terminalDetail = status.error || status.detail || "Backend export failed.";
          setRenderProgress({
            phase: status.phase,
            progress: status.progress,
            detail: terminalDetail,
          });
          setRenderError(terminalDetail);
        }
      } catch (error) {
        if (!disposed) {
          setIsRendering(false);
          setActiveJobId(null);
          setRenderError(describeRenderError(error));
        }
      } finally {
        backendPollInFlightRef.current = false;
      }
    };

    void pollStatus();
    const intervalId = window.setInterval(() => {
      void pollStatus();
    }, 1000);

    return () => {
      disposed = true;
      window.clearInterval(intervalId);
    };
  }, [activeJobId, config.apiBaseUrl, isRendering, renderMode]);

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

  const handleBackendRender = async () => {
    if (!renderPlan) return;

    setRenderMode("backend");
    setIsRendering(true);
    setRenderError(null);
    setBackendStatus(null);
    setPreviewUrl(null);
    setRenderProgress({
      phase: "accepted",
      progress: 2,
      detail: "Uploading render payload to backend.",
    });
    setActiveTab("export");

    try {
      const created = await createRenderJob(config.apiBaseUrl, renderPlan);
      setActiveJobId(created.jobId);
      setRenderProgress({
        phase: "accepted",
        progress: 4,
        detail: "Backend render job queued.",
      });
    } catch (error) {
      setIsRendering(false);
      setActiveJobId(null);
      setRenderError(describeRenderError(error));
    }
  };

  const handleCancelExport = async () => {
    if (!activeJobId || renderMode !== "backend") return;

    try {
      const status = await cancelRenderJob(config.apiBaseUrl, activeJobId);
      setBackendStatus(status);
      setRenderProgress({
        phase: status.phase,
        progress: status.progress,
        detail: status.detail || undefined,
      });
      if (status.status === "cancelled") {
        setIsRendering(false);
        setActiveJobId(null);
        setRenderError(status.error || "Render cancelled by user.");
      }
    } catch (error) {
      setRenderError(describeRenderError(error));
    }
  };

  const handleOpenResult = async () => {
    const jobId = backendStatus?.jobId;
    if (!jobId) return;

    try {
      await revealRenderResult(config.apiBaseUrl, jobId);
    } catch (error) {
      setRenderError(describeRenderError(error));
    }
  };

  const handleDownloadResult = () => {
    if (!previewUrl) return;
    const anchor = document.createElement("a");
    anchor.href = previewUrl;
    anchor.download = "manga-recap-export.mp4";
    anchor.rel = "noopener";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  };

  const blockingIssues = [...validationErrors, ...(renderError ? [renderError] : [])];
  const canCancelBackendExport = renderMode === "backend" && isRendering && !!activeJobId;
  const canCancelExport = canCancelBackendExport;
  const recentBackendLogs = backendStatus?.logs?.slice(-5) ?? [];
  const progressValue = clampProgress(renderProgress?.progress ?? 0);
  const progressPhaseLabel = renderProgress?.phase ? titleCasePhase(renderProgress.phase) : "Preparing Export";
  const progressDetail = renderProgress?.detail || "Preparing render workflow.";
  const progressState = renderError
    ? "failed"
    : isRendering
      ? "running"
      : progressValue >= 100
        ? "completed"
        : "idle";
  const progressToneClass =
    progressState === "failed"
      ? "border-red-500/30 bg-red-500/10"
      : progressState === "completed"
        ? "border-emerald-500/25 bg-emerald-500/10"
        : "border-cyan-400/25 bg-cyan-400/10";
  const progressBarClass =
    progressState === "failed"
      ? "from-red-400 via-red-500 to-orange-400"
      : progressState === "completed"
        ? "from-emerald-300 via-emerald-400 to-cyan-300"
        : "from-cyan-300 via-sky-400 to-blue-500";
  const progressBadgeClass =
    progressState === "failed"
      ? "border-red-400/25 bg-red-500/15 text-red-100"
      : progressState === "completed"
        ? "border-emerald-400/25 bg-emerald-500/15 text-emerald-50"
        : "border-cyan-300/25 bg-cyan-400/15 text-cyan-50";

  return (
    <div className="space-y-6">
      <audio ref={audioRef} className="hidden" />

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
            Timeline & Render
          </h2>
          <p className="text-sm text-white/65">
            Official export now runs through backend native ffmpeg with cinematic keyframed panel motion.
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
            variant="outline"
            onClick={generateStaleVoices}
            disabled={isRendering || staleClipCount === 0}
            className="border-amber-500/30 bg-amber-500/10 px-6 font-bold text-amber-100 hover:bg-amber-500/15"
          >
            <RefreshCw className="h-4 w-4" /> Regenerate stale audio ({staleClipCount})
          </Button>
          {canCancelExport ? (
            <Button variant="destructive" onClick={handleCancelExport} className="px-6 font-bold">
              <XCircle className="h-4 w-4" /> Cancel export
            </Button>
          ) : (
            <Button
              onClick={handleBackendRender}
              disabled={isRendering || !!validationErrors.length}
              className="px-8 font-bold"
            >
              {renderMode === "backend" && isRendering ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Video className="h-4 w-4" />
              )}
              Render MP4
            </Button>
          )}
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

      {blockingIssues.length > 0 && (
        <Card className="rounded-3xl border border-red-500/25 bg-red-500/10 p-5 text-red-50">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <AlertCircle className="h-4 w-4" /> Blocking Issues
          </div>
          <div className="mt-3 space-y-2 text-sm text-red-100/90">
            {blockingIssues.map((error) => (
              <p key={error}>{error}</p>
            ))}
          </div>
        </Card>
      )}

      {voiceError && (
        <Card className="rounded-3xl border border-amber-500/25 bg-amber-500/10 p-5 text-amber-50">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Wand2 className="h-4 w-4" /> Voice Warning
          </div>
          <p className="mt-3 text-sm text-amber-100/90">
            {voiceError}. This does not block backend export unless a narrated clip still lacks ready audio.
          </p>
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
                key={`${item.panelId}-${index}`}
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
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => resetTimelineItemToAuto(index)}
                        disabled={item.scriptStatus !== "edited"}
                        className="rounded-xl"
                      >
                        <RotateCcw className="h-4 w-4" /> Reset auto
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => duplicateTimelineItem(index)}
                        className="rounded-xl"
                      >
                        <Copy className="h-4 w-4" /> Duplicate
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => removeTimelineItem(index)}
                        disabled={timeline.length <= 1}
                        className="rounded-xl border-red-500/30 text-red-100 hover:bg-red-500/10"
                      >
                        <Trash2 className="h-4 w-4" /> Remove
                      </Button>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-[1fr_180px]">
                      <div className="space-y-2">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                          Narration
                        </p>
                        <div className="flex flex-wrap gap-2 text-xs text-white/60">
                          <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1">
                            Script: {item.scriptStatus || "auto"}
                          </span>
                          {item.scriptStatus === "edited" ? (
                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-amber-100">
                              Audio must be regenerated
                            </span>
                          ) : null}
                        </div>
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
                          Active clip duration resolves from ready audio + hold. Backend export applies deterministic
                          keyframed panel motion directly from the compiled render plan.
                        </div>
                        {item.scriptStatus === "edited" && item.scriptBaseline ? (
                          <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/60">
                            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                              Auto Baseline
                            </p>
                            <p>{item.scriptBaseline}</p>
                          </div>
                        ) : null}
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
                    Output Format
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(Object.entries(OUTPUT_PRESETS) as Array<
                      [OutputPreset, (typeof OUTPUT_PRESETS)[OutputPreset]]
                    >).map(([presetKey, preset]) => {
                      const isActive = activeOutputPreset === presetKey;
                      const PresetIcon = presetKey === "vertical" ? RectangleVertical : RectangleHorizontal;

                      return (
                        <Button
                          key={presetKey}
                          variant="outline"
                          onClick={() =>
                            setRenderConfig({
                              outputWidth: preset.outputWidth,
                              aspectRatio: preset.aspectRatio,
                            })
                          }
                          className={getOptionButtonClass(isActive)}
                        >
                          <PresetIcon className="h-4 w-4" />
                          {preset.label}
                        </Button>
                      );
                    })}
                  </div>
                  <p className="text-xs text-white/50">
                    Current preset: {OUTPUT_PRESETS[activeOutputPreset].resolutionLabel}
                  </p>
                </div>

                <div className="space-y-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                    Caption Burn-In
                  </p>
                  <p className="hidden text-xs leading-5 text-white/50">
                    Burned sẽ in narration trực tiếp lên video. Off sẽ xuất MP4 sạch, không có caption hiển thị trên khung hình.
                  </p>
                  <p className="text-xs leading-5 text-white/50">
                    Burned overlays narration text directly on the video. Off exports a clean MP4 without on-frame captions.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={() => setRenderConfig({ captionMode: "off" })}
                      className={getOptionButtonClass(renderConfig.captionMode === "off")}
                    >
                      Off
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setRenderConfig({ captionMode: "burned" })}
                      className={getOptionButtonClass(renderConfig.captionMode === "burned")}
                    >
                      Burned
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                    Export Actions
                  </p>
                  <div className="space-y-3">
                    {canCancelExport ? (
                      <Button
                        size="lg"
                        variant="destructive"
                        onClick={handleCancelExport}
                        className="h-14 w-full rounded-2xl text-lg font-bold"
                      >
                        <XCircle className="h-5 w-5" />
                        Cancel export
                      </Button>
                    ) : null}
                    <Button
                      size="lg"
                      onClick={handleBackendRender}
                      disabled={isRendering || !!validationErrors.length}
                      className="h-14 w-full rounded-2xl text-lg font-bold"
                    >
                      {renderMode === "backend" && isRendering ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <Sparkles className="h-5 w-5" />
                      )}
                      Official backend export
                    </Button>
                  </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/65">
                  Backend export uploads a self-contained render payload to native ffmpeg and applies cinematic
                  keyframed panel motion per clip before final MP4 encoding.
                </div>

                {renderProgress && (
                  <div className={`overflow-hidden rounded-3xl border p-5 ${progressToneClass}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-3">
                          <span className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] ${progressBadgeClass}`}>
                            {progressState}
                          </span>
                          <p className="text-lg font-semibold text-white">{progressPhaseLabel}</p>
                        </div>
                        <p className="max-w-xl text-sm leading-6 text-white/72">{progressDetail}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Progress</p>
                        <p className="mt-2 text-4xl font-black tracking-tight text-white">{progressValue}%</p>
                      </div>
                    </div>

                    <div className="mt-5 space-y-3">
                      <div className="h-3 overflow-hidden rounded-full bg-white/8 ring-1 ring-white/10">
                        <div
                          className={`h-full rounded-full bg-gradient-to-r transition-[width] duration-500 ease-out ${progressBarClass} ${isRendering ? "shadow-[0_0_24px_rgba(56,189,248,0.35)]" : ""}`}
                          style={{ width: `${progressValue}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-white/45">
                        <span>Native Backend Export</span>
                        <span>{progressState === "running" ? "Live" : progressState}</span>
                      </div>
                    </div>
                  </div>
                )}

                {recentBackendLogs.length > 0 && (
                  <div className="rounded-2xl border border-white/10 bg-black/25 p-4 text-sm text-white/70">
                    <p className="font-semibold text-white">Backend logs</p>
                    <div className="mt-3 space-y-2">
                      {recentBackendLogs.map((log) => (
                        <div key={log.id} className="space-y-1">
                          <p>
                            [{log.timestamp}] {log.message}
                          </p>
                          {log.details ? (
                            <pre className="overflow-x-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-black/30 p-3 text-xs text-white/60">
                              {log.details}
                            </pre>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                {previewUrl ? (
                  <Card className="rounded-3xl border border-white/10 bg-black/25 p-4">
                    <div className="mb-3 flex items-center justify-between gap-2 text-sm font-semibold text-white">
                      <div className="flex items-center gap-2">
                        <Volume2 className="h-4 w-4" /> Preview
                      </div>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="outline" onClick={handleOpenResult} className="rounded-xl">
                          <FolderOpen className="h-4 w-4" /> Open folder
                        </Button>
                        <Button size="sm" variant="outline" onClick={handleDownloadResult} className="rounded-xl">
                          <Download className="h-4 w-4" /> Download
                        </Button>
                      </div>
                    </div>
                    <video src={previewUrl} controls className="w-full rounded-2xl border border-white/10 bg-black" />
                  </Card>
                ) : (
                  <Card className="flex min-h-[320px] items-center justify-center rounded-3xl border border-dashed border-white/10 bg-black/20 p-6 text-center text-white/55">
                    Completed backend result preview will appear here.
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
