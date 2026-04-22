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
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { fetchVoiceOptions, generateVoiceAudio, resolveVoiceSampleUrl } from "@/features/voice/api/voiceApi";
import { useVoiceGeneration } from "@/features/voice/hooks/useVoiceGeneration";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { VoiceOptionsResponse } from "@/shared/types";

const PREVIEW_TEXT =
  "Xin chào, đây là đoạn nghe thử để kiểm tra chất giọng kể chuyện, độ cuốn và nhịp review truyện của preset này.";

export function StepVoice() {
  const { config, voiceConfig, setVoiceConfig, timeline, panels, setCurrentStep, isLoading, progress } = useRecapStore();
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
      if (!url) {
        const selectedVoice = activeVoices.find((voice) => voice.key === voiceKey) || null;
        const sampleUrl = resolveVoiceSampleUrl(config.apiBaseUrl, selectedVoice?.sampleUrl);
        if (sampleUrl) {
          url = sampleUrl;
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

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <audio ref={audioRef} className="hidden" />
      <audio ref={previewAudioRef} className="hidden" />

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
            AI Voiceover
          </h2>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <p>Generate narration clips through the backend VieNeu-TTS-0.3B runtime.</p>
            {totalDuration > 0 && !isLoading && (
              <div className="flex items-center gap-1.5 rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 font-medium text-primary">
                <Clock className="h-3.5 w-3.5" />
                Total: {totalDuration.toFixed(1)}s
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
              <Trash2 className="h-4 w-4" /> Clear voice cache
            </Button>
          )}
          <Button
            variant="outline"
            onClick={prevStep}
            disabled={isLoading}
            className="border-white/10 bg-white/5 px-6 font-bold text-white hover:bg-white/10"
          >
            <ChevronLeft className="h-4 w-4" /> Back
          </Button>
          <Button onClick={nextStep} disabled={totalDuration === 0 || isLoading} className="group px-8 font-bold">
            Continue <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Button>
        </div>
      </div>

      {activeVoices.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1 text-sm">
            <span className="font-medium text-muted-foreground">Select Voice Preset</span>
            <span className="text-xs uppercase tracking-[0.2em] text-white/45">{activeProvider?.label || "Voice"}</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
                  className={`group relative flex cursor-pointer flex-col justify-between overflow-hidden rounded-2xl border p-4 transition-all duration-300 ${
                    isSelected
                      ? "border-primary bg-primary/5 shadow-glow"
                      : "border-white/5 bg-white/5 hover:border-white/20 hover:bg-white/10"
                  }`}
                >
                  {isSelected && (
                    <div className="absolute -right-4 -top-4 h-24 w-24 rounded-full bg-primary/20 blur-2xl"></div>
                  )}

                  <div className="relative z-10 mb-6 space-y-1">
                    <h4 className="font-semibold text-white">{voice.label}</h4>
                    {voice.styleTag && (
                      <p className="text-[10px] uppercase tracking-[0.2em] text-primary/80">{voice.styleTag}</p>
                    )}
                    <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                      {voice.description || "Backend voice preset"}
                    </p>
                    {!voice.isAvailable && <p className="text-[10px] text-destructive">Missing assets</p>}
                  </div>

                  <div className="relative z-10 flex items-center justify-between">
                    <div className="flex h-4 w-8 items-center justify-start gap-1">
                      {isPlaying && (
                        <>
                          <div className="h-[8px] w-[3px] animate-[bounce_1s_infinite] rounded-full bg-primary"></div>
                          <div className="h-[14px] w-[3px] animate-[bounce_1s_infinite_0.2s] rounded-full bg-primary/80"></div>
                          <div className="h-[10px] w-[3px] animate-[bounce_1s_infinite_0.4s] rounded-full bg-primary/60"></div>
                        </>
                      )}
                    </div>

                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={(event) => handlePreviewVoice(voice.key, event)}
                      disabled={isLoadingVoice || !voice.isAvailable}
                      className={`h-9 w-9 rounded-full transition-all ${
                        isPlaying
                          ? "bg-primary text-primary-foreground hover:bg-primary/80"
                          : "bg-white/10 text-white hover:bg-white/30 hover:scale-105"
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
            <h3 className="text-xl font-semibold">Create narration audio</h3>
            <p className="max-w-sm px-4 text-muted-foreground">
              Turn the generated script into WAV clips from the backend VieNeu-TTS-0.3B pipeline.
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
              {isLoading ? "Generating audio..." : "Generate all clips"}
            </Button>
            {isLoading && (
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span>PROGRESS</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} className="h-1.5" />
              </div>
            )}
          </div>
        </div>
      ) : (
        <ScrollArea className="glass h-[calc(100vh-220px)] rounded-3xl border border-white/5 bg-white/5 p-2">
          <div className="space-y-3 p-4">
            {timeline.map((item, index) => {
              const panel = panels.find((entry) => entry.id === item.panelId);
              return (
                <Card
                  key={item.panelId}
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
                              <Pause className="mr-2 h-3 w-3" /> Stop
                            </>
                          ) : (
                            <>
                              <Play className="mr-2 h-3 w-3" /> Preview
                            </>
                          )}
                        </Button>
                      ) : (
                        <span className="flex items-center gap-1 text-[10px] text-destructive">
                          <AlertCircle className="h-3 w-3" /> No audio yet
                        </span>
                      )}
                      <span className="text-[10px] uppercase text-muted-foreground">
                        {item.audioDuration ? `${item.audioDuration.toFixed(1)}s` : "--"}
                      </span>
                    </div>
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
