import { Settings2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchVoiceOptions, resolveVoiceSampleUrl } from "@/features/voice/api/voiceApi";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { VoiceOptionsResponse } from "@/shared/types";

const normalizeConfigValue = (value: string): string => {
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

export function SettingsDialog() {
  const { config, setConfig, voiceConfig, setVoiceConfig } = useRecapStore();
  const [open, setOpen] = useState(false);
  const [localConfig, setLocalConfig] = useState(config);
  const [localVoiceConfig, setLocalVoiceConfig] = useState(voiceConfig);
  const [voiceOptions, setVoiceOptions] = useState<VoiceOptionsResponse | null>(null);
  const [voiceOptionsError, setVoiceOptionsError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const previewAudioRef = useRef<HTMLAudioElement>(new Audio());

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    const loadVoiceOptions = async () => {
      try {
        const result = await fetchVoiceOptions(localConfig.apiBaseUrl || config.apiBaseUrl);
        if (!cancelled) {
          setVoiceOptions(result);
          setVoiceOptionsError(null);
          const nextProvider =
            result.providers.find((provider) => provider.id === localVoiceConfig.provider)?.id ||
            result.defaultProvider;
          const providerOption =
            result.providers.find((provider) => provider.id === nextProvider) || result.providers[0];
          const nextVoiceKey =
            providerOption?.voices.find((voice) => voice.key === localVoiceConfig.voiceKey)?.key ||
            providerOption?.defaultVoiceKey ||
            providerOption?.voices[0]?.key ||
            localVoiceConfig.voiceKey;
          setLocalVoiceConfig((current) => ({
            ...current,
            provider: nextProvider,
            voiceKey: nextVoiceKey,
          }));
        }
      } catch (error) {
        if (!cancelled) {
          setVoiceOptions(null);
          setVoiceOptionsError(error instanceof Error ? error.message : "Không thể tải danh sách giọng đọc.");
        }
      }
    };

    void loadVoiceOptions();
    return () => {
      cancelled = true;
    };
  }, [config.apiBaseUrl, localConfig.apiBaseUrl, localVoiceConfig.provider, localVoiceConfig.voiceKey, open]);

  const activeProvider = useMemo(
    () => voiceOptions?.providers.find((provider) => provider.id === localVoiceConfig.provider) || null,
    [localVoiceConfig.provider, voiceOptions]
  );
  const activeVoices = activeProvider?.voices || [];
  const selectedVoice = activeVoices.find((voice) => voice.key === localVoiceConfig.voiceKey) || null;
  const handleSave = () => {
    setConfig({
      ...localConfig,
      apiBaseUrl: normalizeConfigValue(localConfig.apiBaseUrl),
    });
    setVoiceConfig({
      ...localVoiceConfig,
      voiceKey: localVoiceConfig.voiceKey.trim(),
    });
  };

  useEffect(() => {
    const previewAudio = previewAudioRef.current;
    return () => {
      previewAudio.pause();
    };
  }, []);

  const handlePreview = () => {
    const nextPreviewUrl = resolveVoiceSampleUrl(localConfig.apiBaseUrl || config.apiBaseUrl, selectedVoice?.sampleUrl);
    if (!nextPreviewUrl) return;
    if (previewUrl === nextPreviewUrl && !previewAudioRef.current.paused) {
      previewAudioRef.current.pause();
      setPreviewUrl(null);
      return;
    }
    previewAudioRef.current.src = nextPreviewUrl;
    void previewAudioRef.current.play();
    setPreviewUrl(nextPreviewUrl);
    previewAudioRef.current.onended = () => setPreviewUrl(null);
  };

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      previewAudioRef.current.pause();
      setPreviewUrl(null);
      return;
    }

    setLocalConfig(config);
    setLocalVoiceConfig(voiceConfig);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" className="rounded-full">
            <Settings2 className="h-5 w-5" />
          </Button>
        }
      />
      <DialogContent className="glass border-white/10 sm:max-width-[520px]">
        <DialogHeader>
          <DialogTitle>Cài Đặt Hệ Thống</DialogTitle>
          <DialogDescription>Cấu hình kết nối máy chủ và lựa chọn công nghệ giọng đọc mặc định cho dự án.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="apiBaseUrl">Địa chỉ máy chủ (Backend API)</Label>
            <Input
              id="apiBaseUrl"
              placeholder="http://127.0.0.1:8000"
              value={localConfig.apiBaseUrl}
              onChange={(e) => setLocalConfig({ ...localConfig, apiBaseUrl: e.target.value })}
              className="border-white/10 bg-white/5"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="provider">Công nghệ giọng đọc (TTS Provider)</Label>
            <select
              id="provider"
              value={localVoiceConfig.provider}
              onChange={(e) => {
                const nextProvider = e.target.value;
                const providerOption = voiceOptions?.providers.find((provider) => provider.id === nextProvider) || null;
                setLocalVoiceConfig((current) => ({
                  ...current,
                  provider: nextProvider,
                  voiceKey:
                    providerOption?.defaultVoiceKey ||
                    providerOption?.voices[0]?.key ||
                    current.voiceKey,
                }));
              }}
              className="h-10 rounded-md border border-white/10 bg-white/5 px-3 text-sm"
            >
              {(voiceOptions?.providers || []).map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label}
                  {provider.enabled ? "" : " (không khả dụng)"}
                </option>
              ))}
            </select>
            {activeProvider?.statusMessage && (
              <p className="text-xs text-muted-foreground">{activeProvider.statusMessage}</p>
            )}
            {voiceOptionsError && <p className="text-xs text-destructive">{voiceOptionsError}</p>}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="voiceKey">Mẫu giọng mặc định</Label>
            <select
              id="voiceKey"
              value={localVoiceConfig.voiceKey}
              onChange={(e) => setLocalVoiceConfig({ ...localVoiceConfig, voiceKey: e.target.value })}
              className="h-10 rounded-md border border-white/10 bg-white/5 px-3 text-sm"
            >
              {activeVoices.map((voice) => (
                <option key={voice.key} value={voice.key}>
                  {voice.label}
                  {voice.isAvailable ? "" : " (thiếu dữ liệu)"}
                </option>
              ))}
            </select>
            {activeVoices.find((voice) => voice.key === localVoiceConfig.voiceKey)?.statusMessage && (
              <p className="text-xs text-muted-foreground">
                {activeVoices.find((voice) => voice.key === localVoiceConfig.voiceKey)?.statusMessage}
              </p>
            )}
            {selectedVoice?.description && (
              <p className="text-xs text-muted-foreground">{selectedVoice.description}</p>
            )}
            {selectedVoice?.sampleUrl && (
              <Button
                type="button"
                variant="outline"
                onClick={handlePreview}
                className="justify-start border-white/10 bg-white/5"
              >
                {previewUrl ? "Dừng nghe thử" : "Nghe thử mẫu"}
              </Button>
            )}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="speed">Tốc độ đọc</Label>
            <Input
              id="speed"
              type="number"
              min="0.5"
              max="2"
              step="0.1"
              value={localVoiceConfig.speed}
              onChange={(e) =>
                setLocalVoiceConfig({
                  ...localVoiceConfig,
                  speed: Number(e.target.value) || 1.15,
                })
              }
              className="border-white/10 bg-white/5"
            />
          </div>

        </div>

        <DialogFooter>
          <Button onClick={handleSave} className="bg-primary transition-all duration-300 hover:bg-primary/80">
            Lưu cấu hình
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
