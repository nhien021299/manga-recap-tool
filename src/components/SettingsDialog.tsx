import { useRecapStore } from "@/store/useRecapStore";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger,
  DialogDescription,
  DialogFooter
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Settings2 } from "lucide-react";
import { useState, useEffect } from "react";

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
  const { config, setConfig } = useRecapStore();
  const [localConfig, setLocalConfig] = useState(config);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  const handleSave = () => {
    setConfig({
      ...localConfig,
      geminiApiKey: normalizeSecret(localConfig.geminiApiKey),
      elevenLabsApiKey: normalizeSecret(localConfig.elevenLabsApiKey),
      ttsVoiceId: localConfig.ttsVoiceId.trim(),
    });
  };

  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button variant="ghost" size="icon" className="rounded-full">
            <Settings2 className="w-5 h-5" />
          </Button>
        }
      />
      <DialogContent className="sm:max-width-[425px] glass border-white/10">
        <DialogHeader>
          <DialogTitle>Cài đặt hệ thống</DialogTitle>
          <DialogDescription>
            Thiết lập API Keys và cấu hình giọng nói. Dữ liệu được lưu trữ local.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="gemini">Gemini API Key</Label>
            <Input
              id="gemini"
              type="password"
              placeholder="Nhập Gemini API Key..."
              value={localConfig.geminiApiKey}
              onChange={(e) => setLocalConfig({ ...localConfig, geminiApiKey: e.target.value })}
              className="bg-white/5 border-white/10"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="elevenlabs">ElevenLabs API Key</Label>
            <Input
              id="elevenlabs"
              type="password"
              placeholder="Nhập ElevenLabs API Key..."
              value={localConfig.elevenLabsApiKey}
              onChange={(e) => setLocalConfig({ ...localConfig, elevenLabsApiKey: e.target.value })}
              className="bg-white/5 border-white/10"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="voice">Voice ID (ElevenLabs)</Label>
            <Input
              id="voice"
              placeholder="Nhập Voice ID..."
              value={localConfig.ttsVoiceId}
              onChange={(e) => setLocalConfig({ ...localConfig, ttsVoiceId: e.target.value })}
              className="bg-white/5 border-white/10"
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={handleSave} className="bg-primary hover:bg-primary/80 transition-all duration-300">
            Lưu cấu hình
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
