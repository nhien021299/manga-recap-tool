import { Settings2 } from "lucide-react";
import { useEffect, useState } from "react";

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
import { useRecapStore } from "@/shared/storage/useRecapStore";

const normalizeSecret = (value: string): string => {
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

  useEffect(() => {
    setLocalConfig(config);
    setLocalVoiceConfig(voiceConfig);
  }, [config, voiceConfig]);

  const handleSave = () => {
    setConfig({
      ...localConfig,
      apiBaseUrl: normalizeSecret(localConfig.apiBaseUrl),
    });
    setVoiceConfig({
      ...localVoiceConfig,
      elevenLabsApiKey: normalizeSecret(localVoiceConfig.elevenLabsApiKey),
      ttsVoiceId: localVoiceConfig.ttsVoiceId.trim(),
      ttsModel: localVoiceConfig.ttsModel.trim(),
    });
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
          <DialogDescription>
            Configure the local AI backend endpoint. Voice settings remain frontend-side for now.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="apiBaseUrl">AI Backend URL</Label>
            <Input
              id="apiBaseUrl"
              placeholder="http://localhost:8000"
              value={localConfig.apiBaseUrl}
              onChange={(e) => setLocalConfig({ ...localConfig, apiBaseUrl: e.target.value })}
              className="border-white/10 bg-white/5"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="elevenlabs">ElevenLabs API Key</Label>
            <Input
              id="elevenlabs"
              type="password"
              placeholder="Enter ElevenLabs API key"
              value={localVoiceConfig.elevenLabsApiKey}
              onChange={(e) =>
                setLocalVoiceConfig({ ...localVoiceConfig, elevenLabsApiKey: e.target.value })
              }
              className="border-white/10 bg-white/5"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="voice">Voice ID (ElevenLabs)</Label>
            <Input
              id="voice"
              placeholder="Enter voice ID"
              value={localVoiceConfig.ttsVoiceId}
              onChange={(e) => setLocalVoiceConfig({ ...localVoiceConfig, ttsVoiceId: e.target.value })}
              className="border-white/10 bg-white/5"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="ttsModel">TTS Model</Label>
            <Input
              id="ttsModel"
              placeholder="eleven_multilingual_v2"
              value={localVoiceConfig.ttsModel}
              onChange={(e) => setLocalVoiceConfig({ ...localVoiceConfig, ttsModel: e.target.value })}
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
