import { Settings2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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
  const [localConfig, setLocalConfig] = useState(config);
  const [localVoiceConfig, setLocalVoiceConfig] = useState(voiceConfig);
  const [voiceOptions, setVoiceOptions] = useState<VoiceOptionsResponse | null>(null);
  const [voiceOptionsError, setVoiceOptionsError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const previewAudioRef = useState(() => new Audio())[0];

  useEffect(() => {
    setLocalConfig(config);
    setLocalVoiceConfig(voiceConfig);
  }, [config, voiceConfig]);

  useEffect(() => {
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
          setVoiceOptionsError(error instanceof Error ? error.message : "Failed to load voice options.");
        }
      }
    };

    void loadVoiceOptions();
    return () => {
      cancelled = true;
    };
  }, [config.apiBaseUrl, localConfig.apiBaseUrl]);

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
    return () => {
      previewAudioRef.pause();
    };
  }, [previewAudioRef]);

  const handlePreview = () => {
    const nextPreviewUrl = resolveVoiceSampleUrl(localConfig.apiBaseUrl || config.apiBaseUrl, selectedVoice?.sampleUrl);
    if (!nextPreviewUrl) return;
    if (previewUrl === nextPreviewUrl && !previewAudioRef.paused) {
      previewAudioRef.pause();
      setPreviewUrl(null);
      return;
    }
    previewAudioRef.src = nextPreviewUrl;
    void previewAudioRef.play();
    setPreviewUrl(nextPreviewUrl);
    previewAudioRef.onended = () => setPreviewUrl(null);
  };

  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" className="rounded-full">
            <Settings2 className="h-5 w-5" />
          </Button>
        }
      />
      <DialogContent className="glass border-white/10 sm:max-width-[520px]">
        <DialogHeader>
          <DialogTitle>System Settings</DialogTitle>
          <DialogDescription>Configure the backend API and switch between the active VieNeu and F5 voice providers.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="apiBaseUrl">Backend API Base URL</Label>
            <Input
              id="apiBaseUrl"
              placeholder="http://127.0.0.1:8000"
              value={localConfig.apiBaseUrl}
              onChange={(e) => setLocalConfig({ ...localConfig, apiBaseUrl: e.target.value })}
              className="border-white/10 bg-white/5"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="provider">TTS Provider</Label>
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
                  {provider.enabled ? "" : " (unavailable)"}
                </option>
              ))}
            </select>
            {activeProvider?.statusMessage && (
              <p className="text-xs text-muted-foreground">{activeProvider.statusMessage}</p>
            )}
            {voiceOptionsError && <p className="text-xs text-destructive">{voiceOptionsError}</p>}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="voiceKey">Voice Preset</Label>
            <select
              id="voiceKey"
              value={localVoiceConfig.voiceKey}
              onChange={(e) => setLocalVoiceConfig({ ...localVoiceConfig, voiceKey: e.target.value })}
              className="h-10 rounded-md border border-white/10 bg-white/5 px-3 text-sm"
            >
              {activeVoices.map((voice) => (
                <option key={voice.key} value={voice.key}>
                  {voice.label}
                  {voice.isAvailable ? "" : " (missing assets)"}
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
                {previewUrl ? "Stop sample" : "Play sample"}
              </Button>
            )}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="speed">Speed</Label>
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
                  speed: Number(e.target.value) || 1,
                })
              }
              className="border-white/10 bg-white/5"
            />
          </div>

        </div>

        <DialogFooter>
          <Button onClick={handleSave} className="bg-primary transition-all duration-300 hover:bg-primary/80">
            Save Configuration
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
