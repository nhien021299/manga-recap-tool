import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  ChevronLeft,
  Download,
  FolderOpen,
  Loader2,
  RectangleHorizontal,
  RectangleVertical,
  RefreshCw,
  Sparkles,
  Trash2,
  Video,
  Wand2,
  XCircle,
  CheckCircle2,
} from "lucide-react";

import { Player } from "@remotion/player";
import { ChapterRecap, calculateTotalFrames } from "@remotion-project/compositions/ChapterRecap";
import type { VideoDirectionProps, SceneDirection, SceneAsset } from "@remotion-project/types/direction";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  revealRenderResult,
  resolveRenderResultUrl,
} from "@/features/render/api/renderApi";
import { submitNarrationProduction, pollVideoJobStatus, cancelVideoJob, purgeVideoData, suggestEffectMetadata } from "@/features/script/api/scriptApi";
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
    scriptContext,
    renderConfig,
    setRenderConfig,
    setCurrentStep,
    activeJobId,
    setActiveJobId,
    isRendering,
    setIsRendering,
    renderMode,
    setRenderMode,
    renderProgress,
    setRenderProgress,
    renderError,
    setRenderError,
    previewUrl,
    setPreviewUrl,
    backendStatus,
    setBackendStatus,
    setTimeline,
  } = useRecapStore();
  const [isSuggesting, setIsSuggesting] = useState(false);
  const { generateStaleVoices, error: voiceError } = useVoiceGeneration();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const backendPollInFlightRef = useRef(false);

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
        const videoStatus = await pollVideoJobStatus(config.apiBaseUrl, activeJobId);
        if (disposed) return;

        const status: RenderJobStatusResponse = {
          jobId: videoStatus.job_id,
          status: videoStatus.phase === "completed" 
            ? "completed" 
            : (videoStatus.phase === "failed" ? "failed" : "running"),
          phase: videoStatus.phase,
          progress: videoStatus.progress,
          detail: videoStatus.detail,
          error: videoStatus.error || undefined,
          downloadUrl: videoStatus.download_url || undefined,
          logs: [],
        };

        setBackendStatus(status);
        setRenderProgress({
          phase: status.phase,
          progress: status.progress,
          detail: status.detail || undefined,
        });

        if (status.status === "completed") {
          setIsRendering(false);
          setActiveJobId(null);
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

  const handleSuggestEffects = async () => {
    if (!timeline.length) return;
    setIsSuggesting(true);
    try {
      const scenes = timeline
        .filter((item) => item.enabled !== false)
        .map((item, index) => ({
          scene: index + 1,
          title: `Scene ${index + 1}`,
          narration: item.scriptItem.voiceover_text,
          duration_seconds: item.audioDuration || 0,
          dialogue: item.scriptItem.dialogue_text || null,
        }));

      const response = await suggestEffectMetadata(config.apiBaseUrl, scenes);
      
      const newTimeline = timeline.map((item, index) => {
        const suggestion = response.scenes.find(s => s.scene === index + 1);
        if (suggestion) {
          return {
            ...item,
            sceneType: suggestion.scene_type,
            mood: suggestion.mood,
            motionPreset: suggestion.motion_preset,
            motionIntensity: suggestion.motion_intensity,
            transition: suggestion.transition,
            transitionDurationMs: suggestion.transition_duration_ms,
            vfxTags: suggestion.vfx_tags,
            sfxTags: suggestion.sfx_tags,
            subtitleMood: suggestion.subtitle_mood || suggestion.mood,
          };
        }
        return item;
      });
      
      setTimeline(newTimeline);
    } catch (error) {
      setRenderError(describeRenderError(error));
    } finally {
      setIsSuggesting(false);
    }
  };

  const handleBackendRender = async () => {
    if (!timeline.length) return;

    setRenderMode("backend");
    setIsRendering(true);
    setRenderError(null);
    setBackendStatus(null);
    setPreviewUrl(null);
    setRenderProgress({
      phase: "accepted",
      progress: 2,
      detail: "Preparing narration package and assets...",
    });

    try {
      const narrationPayload = {
        project: scriptContext.mangaName || "Manga Recap",
        chapter: Number(scriptContext.chapterId) || 1,
        language: scriptContext.language || "vi",
        scenes: timeline
          .filter((item) => item.enabled !== false)
          .map((item, index) => ({
            scene: index + 1,
            title: `Scene ${index + 1}`,
            narration: item.scriptItem.voiceover_text,
            duration_seconds: item.audioDuration || 0,
            dialogue: item.scriptItem.dialogue_text || null,
            scene_type: item.sceneType,
            mood: item.mood,
            motion_preset: item.motionPreset,
            motion_intensity: item.motionIntensity,
            transition: item.transition,
            transition_duration_ms: item.transitionDurationMs,
            vfx_tags: item.vfxTags,
            sfx_tags: item.sfxTags,
            subtitle_mood: item.subtitleMood,
          })),
      };

      const voiceConfig = useRecapStore.getState().voiceConfig;
      const response = await submitNarrationProduction(
        config.apiBaseUrl,
        narrationPayload,
        panels,
        {
          voiceKey: voiceConfig.voiceKey,
          speed: voiceConfig.speed,
          provider: voiceConfig.provider,
        }
      );

      setActiveJobId(response.job_id);
      setRenderProgress({
        phase: response.phase,
        progress: response.progress,
        detail: response.detail || "Video production job started.",
      });
    } catch (error) {
      setIsRendering(false);
      setActiveJobId(null);
      setRenderError(describeRenderError(error));
    }
  };

  const handlePurgeCache = async () => {
    if (!window.confirm("Bạn có chắc chắn muốn dừng toàn bộ Job và xóa sạch cache không?")) return;
    
    try {
      await purgeVideoData(config.apiBaseUrl);
      setIsRendering(false);
      setActiveJobId(null);
      setBackendStatus(null);
      setRenderProgress(null);
      setPreviewUrl(null);
      alert("Đã dừng toàn bộ job và xóa sạch cache hệ thống.");
    } catch (error) {
      setRenderError(describeRenderError(error));
    }
  };

  const handleCancelExport = async () => {
    if (!activeJobId || renderMode !== "backend") return;

    try {
      const statusResponse = await cancelVideoJob(config.apiBaseUrl, activeJobId);
      
      const status: RenderJobStatusResponse = {
        jobId: statusResponse.job_id,
        status: statusResponse.phase === "cancelled" ? "cancelled" : "running",
        phase: statusResponse.phase,
        progress: statusResponse.progress,
        detail: statusResponse.detail,
        error: statusResponse.error || undefined,
        downloadUrl: statusResponse.download_url || undefined,
        logs: [],
      };

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

  // --- Remotion Player Integration ---
  const playerProps = useMemo<VideoDirectionProps | null>(() => {
    if (!timeline.length || !panels.length) return null;

    const plan = buildRenderPlan(timeline, panels, renderConfig);
    
    const directionScenes: SceneDirection[] = plan.clips.map((clip, idx) => {
      // Use previous clip's transition for transition_in (cinematic flow)
      const prevClip = idx > 0 ? plan.clips[idx - 1] : null;

      // Brief visual lead-in before audio starts (shorter = tighter pacing)
      const audioStartMs = idx === 0 ? 350 : 150;

      // Map mood to color grade
      const colorGrade = clip.mood === "ominous" || clip.mood === "tense" ? "cold_blue" :
                         clip.mood === "violent" || clip.mood === "epic" ? "warm_firelight" :
                         clip.mood === "tragic" || clip.mood === "lonely" ? "cold_dusk" :
                         clip.mood === "mystical" ? "dark_jade" : "neutral";

      return {
        scene: clip.orderIndex + 1,
        // CRITICAL: scene must be long enough for audio_start_delay + full audio + hold
        total_duration_ms: clip.durationMs + audioStartMs,
        audio_start_ms: audioStartMs,
        keyframes: [], // Plan Phase 1: no custom keyframes, motion from resolver
        transition_in: idx === 0 ? null : {
          type: prevClip?.transition || "crossfade",
          duration_ms: prevClip?.transitionDurationMs || 500,
          params: {},
        },
        transition_out: { 
          type: clip.transition, 
          duration_ms: clip.transitionDurationMs, 
          params: {},
        },
        text_overlays: clip.text_overlays || [],
        color_grade: colorGrade,
        motion_preset: clip.motionPreset,
        motion_intensity: clip.motionIntensity,
        vfx_tags: clip.vfxTags || [],
        sfx_tags: clip.sfxTags || [],
      };
    });

    const assets: SceneAsset[] = plan.clips.map((clip, idx) => {
      return {
        scene: clip.orderIndex + 1,
        title: `Scene ${clip.orderIndex + 1}`,
        imagePath: clip.panel.base64 || clip.panel.thumbnail || null,
        audioPath: clip.audioBlob ? URL.createObjectURL(clip.audioBlob) : null,
        dialogueAudioPath: null,
        // Audio duration = clip duration minus hold (audio portion only)
        audioDurationMs: Math.max(0, clip.durationMs - (clip.holdAfterMs || 250)),
        dialogueDurationMs: null,
      };
    });

    return {
      chapter: Number(scriptContext.chapterId) || 1,
      total_duration_ms: plan.totalDurationMs,
      fps: plan.frameRate,
      width: plan.outputWidth,
      height: plan.outputHeight,
      scenes: directionScenes,
      assets,
      publicDir: "",
      global_settings: {},
    };
  }, [timeline, panels, renderConfig, scriptContext.chapterId]);

  const playerDurationFrames = useMemo(() => {
    if (!playerProps) return 1;
    return calculateTotalFrames(playerProps.scenes, playerProps.fps);
  }, [playerProps]);

  return (
    <div className="space-y-6">
      <audio ref={audioRef} className="hidden" />

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
            Dựng Phim & Xuất Bản
          </h2>
          <p className="text-sm text-white/65">
            Quá trình xuất video được thực hiện bằng engine Remotion với hiệu ứng chuyển động mượt mà và chất lượng cao.
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
            <RefreshCw className="h-4 w-4" /> Cập nhật giọng đọc ({staleClipCount})
          </Button>
          {canCancelExport ? (
            <Button variant="destructive" onClick={handleCancelExport} className="px-6 font-bold">
              <XCircle className="h-4 w-4" /> Hủy xuất bản
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
              Xuất Video MP4
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="glass rounded-3xl border-white/10 bg-white/5 p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Số cảnh quay</p>
          <p className="mt-2 text-2xl font-bold text-white">{activeClipCount}</p>
        </Card>
        <Card className="glass rounded-3xl border-white/10 bg-white/5 p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Tổng thời lượng</p>
          <p className="mt-2 text-2xl font-bold text-white">{formatSeconds(totalDurationMs)}</p>
        </Card>
        <Card className="glass rounded-3xl border-white/10 bg-white/5 p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Độ phân giải</p>
          <p className="mt-2 text-2xl font-bold text-white">
            {renderConfig.outputWidth} x {Math.round(renderConfig.outputWidth / renderConfig.aspectRatio)}
          </p>
        </Card>
      </div>

      <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6 overflow-hidden">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/20 text-purple-400">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Kế Hoạch Hiệu Ứng (AI Suggestion)</h3>
              <p className="text-xs text-white/45">Bản phác thảo phong cách và chuyển động được Gemini gợi ý cho từng phân cảnh.</p>
            </div>
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleSuggestEffects}
            disabled={isSuggesting || isRendering}
            className="rounded-xl border-purple-500/30 bg-purple-500/5 text-purple-100 hover:bg-purple-500/10"
          >
            {isSuggesting ? <Loader2 className="mr-2 h-3 w-3 animate-spin" /> : <Wand2 className="mr-2 h-3 w-3" />}
            Refresh Plan
          </Button>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-white/5 bg-black/20">
          <table className="w-full text-left text-sm text-white/80">
            <thead>
              <tr className="border-b border-white/5 bg-white/5 text-[10px] font-semibold uppercase tracking-wider text-white/40">
                <th className="px-4 py-3">Cảnh</th>
                <th className="px-4 py-3">Loại & Tâm trạng</th>
                <th className="px-4 py-3">Chuyển động</th>
                <th className="px-4 py-3">Chuyển cảnh</th>
                <th className="px-4 py-3 text-right">VFX/SFX</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {timeline.map((item, idx) => (
                <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-4 font-mono text-xs font-bold text-white/50">
                    #{idx + 1}
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex flex-col gap-1">
                      <span className="font-semibold text-white">{item.sceneType || "default"}</span>
                      <span className="text-[10px] text-white/40 uppercase tracking-wider italic">{item.mood || "normal"}</span>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex flex-col gap-1">
                      <span className="text-xs">{item.motionPreset || "push_in_center"}</span>
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 flex-1 rounded-full bg-white/5 overflow-hidden">
                          <div 
                            className="h-full bg-cyan-400/60" 
                            style={{ width: `${(item.motionIntensity || 0.7) * 100}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-white/40">{item.motionIntensity || 0.7}</span>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex flex-col gap-1">
                      <span className="text-xs">{item.transition || "crossfade"}</span>
                      <span className="text-[10px] text-white/40">{item.transitionDurationMs || 500}ms</span>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-right">
                    <div className="flex flex-wrap justify-end gap-1">
                      {((item.vfxTags?.length || 0) + (item.sfxTags?.length || 0)) > 0 ? (
                        <>
                          {item.vfxTags?.map(tag => (
                            <span key={tag} className="rounded-md border border-cyan-500/20 bg-cyan-500/10 px-1.5 py-0.5 text-[9px] text-cyan-300">
                              {tag}
                            </span>
                          ))}
                          {item.sfxTags?.map(tag => (
                            <span key={tag} className="rounded-md border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 text-[9px] text-amber-300">
                              {tag}
                            </span>
                          ))}
                        </>
                      ) : (
                        <span className="text-[10px] text-white/20">—</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {blockingIssues.length > 0 && (
        <Card className="rounded-3xl border border-red-500/25 bg-red-500/10 p-5 text-red-50">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <AlertCircle className="h-4 w-4" /> Vấn đề cần xử lý
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

      <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-5">
            <div className="space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                Định dạng đầu ra
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
                Chèn phụ đề video
              </p>
              <p className="text-xs leading-5 text-white/50">
                'Bật' sẽ in trực tiếp lời thoại lên video. 'Tắt' sẽ xuất video sạch không có chữ.
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setRenderConfig({ captionMode: "off" })}
                  className={getOptionButtonClass(renderConfig.captionMode === "off")}
                >
                  Tắt
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setRenderConfig({ captionMode: "burned" })}
                  className={getOptionButtonClass(renderConfig.captionMode === "burned")}
                >
                  Bật
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">
                Thao tác xuất bản
              </p>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {canCancelExport && (
                    <Button
                      size="lg"
                      variant="destructive"
                      onClick={handleCancelExport}
                      className="h-14 rounded-2xl text-lg font-bold"
                    >
                      <XCircle className="h-5 w-5" />
                      Hủy xuất bản
                    </Button>
                  )}
                  <Button
                    size="lg"
                    variant="outline"
                    onClick={handlePurgeCache}
                    className={`h-14 rounded-2xl text-lg font-bold border-red-500/30 bg-red-500/5 text-red-400 hover:bg-red-500/10 ${!canCancelExport ? "col-span-2" : ""}`}
                  >
                    <Trash2 className="h-5 w-5" />
                    Dừng & Xóa Cache
                  </Button>
                </div>

                <div className="space-y-3">
                  <Button
                    size="lg"
                    variant="outline"
                    onClick={handleSuggestEffects}
                    disabled={isSuggesting || isRendering || !timeline.length}
                    className="h-14 w-full rounded-2xl border-purple-500/30 bg-purple-500/5 text-purple-100 hover:bg-purple-500/10 font-bold"
                  >
                    {isSuggesting ? (
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    ) : (
                      <Wand2 className="mr-2 h-5 w-5" />
                    )}
                    Gợi ý Effect bằng AI (Gemini)
                  </Button>

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
                  Bắt đầu xuất video
                </Button>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/65">
              Hệ thống sẽ tổng hợp kịch bản, âm thanh và hình ảnh để tạo video MP4 hoàn chỉnh bằng engine Remotion.
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
                    <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/45">Tiến độ</p>
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
                    <span>Engine Remotion</span>
                    <span>{progressState === "running" ? "Đang chạy" : (progressState === "completed" ? "Hoàn tất" : "Lỗi")}</span>
                  </div>
                </div>
              </div>
            )}

            {previewUrl && (
              <div className="space-y-4 rounded-3xl border border-emerald-500/20 bg-emerald-500/5 p-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400">
                      <CheckCircle2 className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">Xuất bản thành công!</p>
                      <p className="text-xs text-white/45">Video đã sẵn sàng để tải về hoặc xem trước.</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={handleOpenResult} className="rounded-xl border-white/10 bg-white/5">
                      <FolderOpen className="mr-2 h-4 w-4" /> Mở thư mục
                    </Button>
                    <Button variant="secondary" size="sm" onClick={handleDownloadResult} className="rounded-xl bg-emerald-500 text-white hover:bg-emerald-600">
                      <Download className="mr-2 h-4 w-4" /> Tải về .MP4
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="relative aspect-video overflow-hidden rounded-2xl border border-white/10 bg-black/40 shadow-2xl">
            {previewUrl ? (
              <video src={previewUrl} controls className="h-full w-full object-contain" />
            ) : playerProps ? (
              <div className="h-full w-full">
                <Player
                  key={JSON.stringify(playerProps.scenes.map(s => s.motion_preset + s.transition_out?.type))}
                  component={ChapterRecap}
                  inputProps={playerProps}
                  durationInFrames={playerDurationFrames}
                  fps={playerProps.fps}
                  compositionWidth={playerProps.width}
                  compositionHeight={playerProps.height}
                  style={{
                    width: "100%",
                    height: "100%",
                  }}
                  controls
                  loop
                />
              </div>
            ) : (
              <div className="flex h-full w-full flex-col items-center justify-center space-y-3 text-white/20">
                <Video className="h-12 w-12" />
                <p className="text-sm font-medium">Video Preview Area</p>
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
