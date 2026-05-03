import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Trash2,
  Volume2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Slider } from "@/components/ui/slider";
import { fetchVoiceOptions, generateVoiceAudio } from "@/features/voice/api/voiceApi";
import { useVoiceGeneration } from "@/features/voice/hooks/useVoiceGeneration";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { VoiceOptionsResponse } from "@/shared/types";

const PREVIEW_TEXT =
  "Xin chào, đây là đoạn nghe thử để kiểm tra chất giọng kể chuyện, độ cuốn và nhịp review truyện của preset này.";

const MIN_VOICE_SPEED = 0.8;
const MAX_VOICE_SPEED = 3.0;
const SPEED_STEP = 0.05;

const clampVoiceSpeed = (value: number): number =>
  Math.min(MAX_VOICE_SPEED, Math.max(MIN_VOICE_SPEED, Number(value.toFixed(2))));

export function StepVoice() {
  const { config, voiceConfig, setVoiceConfig, timeline, panels, setCurrentStep, isLoading, progress, currentVoiceGeneration } =
    useRecapStore();
  const { generateAllVoices, generateSingleVoice, clearAllVoices, error } = useVoiceGeneration();
  const [playingIdx, setPlayingIdx] = useState<number | null>(null);
  const [voiceOptions, setVoiceOptions] = useState<VoiceOptionsResponse | null>(null);
  const [playingPreview, setPlayingPreview] = useState<string | null>(null);
  const [isPreviewingKey, setIsPreviewingKey] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const previewCacheRef = useRef<Record<string, string>>({});

  const nextStep = () => setCurrentStep("render");
  const prevStep = () => setCurrentStep("script");

  const togglePlay = (index: number, url: string) => {
    if (playingIdx === index) {
      audioRef.current?.pause();
      setPlayingIdx(null);
      return;
    }

    if (!audioRef.current) return;
    audioRef.current.src = url;
    void audioRef.current.play();
    setPlayingIdx(index);
    audioRef.current.onended = () => setPlayingIdx(null);
  };

  useEffect(() => {
    let active = true;
    fetchVoiceOptions(config.apiBaseUrl)
      .then((options) => {
        if (active) setVoiceOptions(options);
      })
      .catch((fetchError) => {
        console.error(fetchError);
      });
    return () => {
      active = false;
    };
  }, [config.apiBaseUrl]);

  const activeProvider =
    voiceOptions?.providers.find((provider) => provider.id === voiceConfig.provider) || voiceOptions?.providers[0] || null;
  const activeVoices = activeProvider?.voices || [];
  const staleClipCount = timeline.filter((item) => item.audioStatus === "stale").length;

  const handleSpeedChange = (nextSpeed: number) => {
    setVoiceConfig({ speed: clampVoiceSpeed(nextSpeed) });
  };

  const handlePreviewVoice = async (voiceKey: string, event: React.MouseEvent) => {
    event.stopPropagation();

    if (playingPreview === voiceKey) {
      previewAudioRef.current?.pause();
      setPlayingPreview(null);
      return;
    }

    previewAudioRef.current?.pause();
    setPlayingPreview(null);
    setIsPreviewingKey(voiceKey);

    try {
      const cacheKey = JSON.stringify({
        provider: activeProvider?.id || voiceConfig.provider,
        voiceKey,
        speed: voiceConfig.speed,
        apiBaseUrl: config.apiBaseUrl,
      });

      let url = previewCacheRef.current[cacheKey];
      const targetVoice = activeVoices.find(v => v.key === voiceKey);

      if (!url) {
        if (targetVoice?.sampleUrl) {
          url = targetVoice.sampleUrl.startsWith("http") 
            ? targetVoice.sampleUrl 
            : `${config.apiBaseUrl}${targetVoice.sampleUrl}`;
        } else {
          const blob = await generateVoiceAudio(config.apiBaseUrl, {
            text: PREVIEW_TEXT,
            provider: activeProvider?.id || voiceConfig.provider,
            voiceKey,
            speed: voiceConfig.speed,
          });
          url = URL.createObjectURL(blob);
          previewCacheRef.current[cacheKey] = url;
        }
      }

      if (previewAudioRef.current) {
        previewAudioRef.current.src = url;
        previewAudioRef.current.playbackRate = targetVoice?.sampleUrl ? voiceConfig.speed : 1.0;
        previewAudioRef.current.preservesPitch = true; // Try to preserve pitch when changing playbackRate
        previewAudioRef.current.onended = () => setPlayingPreview(null);
        void previewAudioRef.current.play();
        setPlayingPreview(voiceKey);
      }
    } catch (previewError) {
      console.error("Preview failed:", previewError);
    } finally {
      setIsPreviewingKey(null);
    }
  };

  const totalDuration = timeline.reduce((total, item) => total + (item.audioDuration || 0), 0);
  const activePanel = currentVoiceGeneration
    ? panels.find((entry) => entry.id === currentVoiceGeneration.panelId) || null
    : null;

  useEffect(() => {
    return () => {
      previewAudioRef.current?.pause();
      Object.values(previewCacheRef.current).forEach((url) => {
        if (url.startsWith("blob:")) {
          URL.revokeObjectURL(url);
        }
      });
    };
  }, []);

  return (
    <div className="space-y-6">
      <audio ref={audioRef} className="hidden" />
      <audio ref={previewAudioRef} className="hidden" />

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
            Lồng Tiếng AI
          </h2>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <p>Tạo giọng đọc thuyết minh tự động bằng AI (VieNeu TTS).</p>
            {totalDuration > 0 && !isLoading && (
              <div className="flex items-center gap-1.5 rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 font-medium text-primary">
                <Clock className="h-3.5 w-3.5" />
                Tổng: {totalDuration.toFixed(1)}s
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {timeline.some((item) => item.audioUrl) && !isLoading && (
            <Button
              variant="outline"
              onClick={clearAllVoices}
              className="border-red-500/30 bg-red-500/10 px-6 font-bold text-red-200 hover:bg-red-500/15"
            >
              <Trash2 className="h-4 w-4" /> Xóa giọng cũ
            </Button>
          )}
          <Button
            variant="outline"
            onClick={prevStep}
            disabled={isLoading}
            className="border-white/10 bg-white/5 px-6 font-bold text-white hover:bg-white/10"
          >
            <ChevronLeft className="h-4 w-4" /> Quay lại
          </Button>
          <Button onClick={nextStep} disabled={timeline.length === 0 || isLoading} className="group px-8 font-bold">
            Tiếp tục <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Button>
        </div>
      </div>

      {activeVoices.length > 0 && (
        <div className="space-y-3">
          <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
            {activeVoices.map((voice) => {
              const isSelected = voiceConfig.voiceKey === voice.key;
              const isPlaying = playingPreview === voice.key;
              const isLoadingVoice = isPreviewingKey === voice.key;

              return (
                <div
                  key={voice.key}
                  onClick={() =>
                    setVoiceConfig({
                      provider: activeProvider?.id || voiceConfig.provider,
                      voiceKey: voice.key,
                    })
                  }
                  className={`group relative flex cursor-pointer items-center justify-between overflow-hidden rounded-2xl border px-4 py-2.5 transition-all duration-300 ${
                    isSelected
                      ? "border-primary/40 bg-primary/10 shadow-glow-sm"
                      : "border-white/5 bg-white/5 hover:border-white/20 hover:bg-white/10"
                  }`}
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold transition-colors ${
                        isSelected
                          ? "border-primary/40 bg-primary/20 text-primary shadow-sm"
                          : "border-white/10 bg-white/5 text-white/40"
                      }`}
                    >
                      {voice.label.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex flex-col overflow-hidden">
                      <h4 className="truncate text-sm font-bold text-white">{voice.label}</h4>
                      <p className="text-[9px] uppercase tracking-[0.1em] text-white/40">
                        {voice.styleTag || "Default Preset"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {isSelected && (
                      <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/40 px-2.5 py-1 backdrop-blur-md">
                        <span className="text-[9px] font-bold uppercase tracking-tight text-white/30">Speed</span>
                        <div className="flex items-center">
                          <Input
                            type="number"
                            min={MIN_VOICE_SPEED}
                            max={MAX_VOICE_SPEED}
                            step={SPEED_STEP}
                            value={voiceConfig.speed}
                            onChange={(event) => handleSpeedChange(Number(event.target.value) || 1)}
                            onClick={(event) => event.stopPropagation()}
                            className="h-5 w-12 border-none bg-transparent p-0 text-center font-mono text-xs font-bold text-primary focus-visible:ring-0"
                          />
                          <span className="text-[10px] font-bold text-primary/50">x</span>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      {isPlaying && (
                        <div className="flex items-center gap-0.5 px-1">
                          <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary"></div>
                          <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary/60 [animation-delay:0.2s]"></div>
                        </div>
                      )}
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={(event) => handlePreviewVoice(voice.key, event)}
                        disabled={isLoadingVoice || !voice.isAvailable}
                        className={`h-8 w-8 rounded-full shadow-sm transition-all ${
                          isPlaying
                            ? "bg-primary text-primary-foreground scale-105"
                            : "bg-white/10 text-white hover:bg-white/20 hover:scale-105"
                        }`}
                      >
                        {isLoadingVoice ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : isPlaying ? (
                          <Pause className="h-4 w-4" />
                        ) : (
                          <Play className="ml-0.5 h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {isLoading || !timeline.some((item) => item.audioUrl) ? (
        <div className="flex h-[400px] flex-col items-center justify-center space-y-6 rounded-3xl border border-dashed border-white/10 bg-white/5">
          <div className="rounded-full bg-primary/10 p-8">
            <Volume2 className="h-16 w-16 text-primary" />
          </div>
          <div className="space-y-2 text-center">
            <h3 className="text-xl font-semibold">Tạo giọng đọc thuyết minh</h3>
            <p className="max-w-sm px-4 text-muted-foreground">
              Chuyển đổi kịch bản thành các tệp âm thanh WAV chất lượng cao bằng AI.
            </p>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-4 py-2 text-destructive">
              <AlertCircle className="h-4 w-4" />
              <span className="text-sm font-medium">{error}</span>
            </div>
          )}

          <div className="w-full max-w-xs space-y-4">
            <Button
              size="lg"
              onClick={generateAllVoices}
              disabled={isLoading}
              className="h-14 w-full rounded-2xl border-none bg-primary text-lg font-bold text-primary-foreground shadow-glow transition-all hover:opacity-90 active:scale-[0.98]"
            >
              {isLoading ? "Đang tạo giọng đọc..." : "Bắt đầu lồng tiếng toàn bộ"}
            </Button>
            {isLoading && (
              <div className="space-y-3">
                <div className="flex justify-between text-xs font-mono">
                  <span>PROGRESS</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} className="h-1.5" />
                {currentVoiceGeneration && (
                  <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-left">
                    <div className="flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.2em] text-white/50">
                      <span>
                        Clip {currentVoiceGeneration.currentIndex}/{currentVoiceGeneration.totalCount}
                      </span>
                      <span>{currentVoiceGeneration.voiceKey}</span>
                    </div>
                    <div className="mt-2 flex items-center gap-3">
                      {activePanel?.thumbnail ? (
                        <img
                          src={activePanel.thumbnail}
                          alt={`Panel ${currentVoiceGeneration.panelOrder}`}
                          className="h-12 w-12 rounded-lg border border-white/10 object-cover"
                        />
                      ) : (
                        <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-[10px] text-white/50">
                          #{currentVoiceGeneration.panelOrder}
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-white">Panel {currentVoiceGeneration.panelOrder}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {currentVoiceGeneration.textLength} chars, panelId {currentVoiceGeneration.panelId}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        <ScrollArea className="glass h-[calc(100vh-220px)] rounded-3xl border border-white/5 bg-white/5 p-2">
          <div className="space-y-3 p-4">
            {timeline.map((item, index) => {
              const panel = panels.find((entry) => entry.id === item.panelId);
              const isCurrentGenerating = currentVoiceGeneration?.panelId === item.panelId;
              return (
                <Card
                  key={`${item.panelId}-${index}`}
                  className="group flex items-center gap-4 rounded-2xl border-white/5 bg-background p-3 transition-all hover:border-primary/20"
                >
                  <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl border border-white/5 bg-black">
                    <img src={panel?.thumbnail} className="h-full w-full object-cover" />
                  </div>

                  <div className="flex-1 space-y-1">
                    <p className="line-clamp-2 text-sm font-medium italic leading-relaxed text-muted-foreground">
                      "{item.scriptItem.voiceover_text}"
                    </p>
                    <div className="flex items-center gap-3">
                      {item.audioUrl ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          className="h-8 rounded-full border-white/10 bg-white/5 hover:bg-white/10"
                          onClick={() => togglePlay(index, item.audioUrl!)}
                        >
                          {playingIdx === index ? (
                            <>
                              <Pause className="mr-2 h-3 w-3" /> Dừng
                            </>
                          ) : (
                            <>
                              <Play className="mr-2 h-3 w-3" /> Nghe thử
                            </>
                          )}
                        </Button>
                      ) : (
                        <span className="flex items-center gap-1 text-[10px] text-destructive">
                          <AlertCircle className="h-3 w-3" /> Chưa có âm thanh
                        </span>
                      )}
                      <span className="text-[10px] uppercase text-muted-foreground">
                        {item.audioDuration ? `${item.audioDuration.toFixed(1)}s` : "--"}
                      </span>
                      {isCurrentGenerating && (
                        <span className="flex items-center gap-1 text-[10px] uppercase tracking-[0.18em] text-primary">
                          <Loader2 className="h-3 w-3 animate-spin" /> Generating now
                        </span>
                      )}
                    </div>
                    {item.audioChunks && item.audioChunks.length > 0 && (
                      <div className="mt-3 flex flex-col gap-2 rounded-xl border border-white/5 bg-black/20 p-3">
                        {item.audioChunks.map((chunk) => (
                          <div
                            key={chunk.i}
                            className="flex flex-col gap-1 border-b border-white/5 pb-2 last:border-0 last:pb-0"
                          >
                            <span className="font-mono text-[10px] text-primary/70">
                              Chunk {chunk.i} ({chunk.w}w)
                            </span>
                            <span className="text-xs text-muted-foreground leading-relaxed">
                              {chunk.text}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => generateSingleVoice(index)}
                    className="rounded-full opacity-0 transition-opacity group-hover:opacity-100"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </Card>
              );
            })}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
