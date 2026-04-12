import { useRecapStore } from "@/store/useRecapStore";
import { useScriptGeneration } from "@/hooks/useScriptGeneration";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { 
  ChevronRight, 
  ChevronLeft, 
  Wand2, 
  Bot,
  AlertCircle,
  Music,
  User,
  Type,
  History,
  Ghost
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { useState, useMemo } from "react";

export function StepScript() {
  const { 
    timeline, 
    panels, 
    scriptContext, 
    setScriptContext, 
    updateTimelineItem, 
    setTimeline,
    setCurrentStep, 
    isLoading 
  } = useRecapStore();
  
  const { generateScript, error } = useScriptGeneration();
  const [unknownCharId, setUnknownCharId] = useState<string | null>(null);
  const [replacementName, setReplacementName] = useState("");

  const nextStep = () => setCurrentStep('voice');
  const prevStep = () => setCurrentStep('extract');

  // Logic: Find all [...] placeholders in the current timeline
  const unknownCharacters = useMemo(() => {
    const found = new Set<string>();
    timeline.forEach(item => {
      const match = item.scriptItem.speaker.match(/\[(.*?)\]/);
      if (match) found.add(match[0]);
      
      // Also check dialogue for placeholders
      const diagMatch = item.scriptItem.dialogue.match(/\[(.*?)\]/);
      if (diagMatch) found.add(diagMatch[0]);
    });
    return Array.from(found);
  }, [timeline]);

  const handleReplaceCharacter = (placeholder: string) => {
    if (!replacementName) return;
    
    const newTimeline = timeline.map(item => ({
      ...item,
      scriptItem: {
        ...item.scriptItem,
        speaker: item.scriptItem.speaker.replace(placeholder, replacementName),
        dialogue: item.scriptItem.dialogue.replace(new RegExp(placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), replacementName)
      }
    }));
    
    setTimeline(newTimeline);
    setUnknownCharId(null);
    setReplacementName("");
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
            Kịch bản Recap
          </h2>
          <p className="text-muted-foreground">AI viết kịch bản dựa trên diễn biến hình ảnh. Có thể chỉnh sửa thủ công.</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={prevStep} className="rounded-xl border-white/10">
            <ChevronLeft className="w-4 h-4 mr-2" /> Quay lại
          </Button>
          <Button onClick={nextStep} disabled={timeline.length === 0} className="bg-primary hover:bg-primary/90 rounded-xl shadow-lg">
            Tiếp tục <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>

      {timeline.length === 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">
          {/* Step 1: Global Context Form */}
          <Card className="p-8 bg-white/5 border-white/10 rounded-3xl space-y-6 glass">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/20">
                <History className="w-5 h-5 text-primary" />
              </div>
              <h3 className="text-xl font-bold">Thiết lập Bối cảnh</h3>
            </div>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="mangaName">Tên truyện</Label>
                <Input 
                  id="mangaName" 
                  placeholder="VD: Cầu Ma, Võ Luyện Đỉnh Phong..." 
                  value={scriptContext.mangaName}
                  onChange={(e) => setScriptContext({ mangaName: e.target.value })}
                  className="bg-white/5 border-white/10 h-12 rounded-xl"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="mainChar">Nhân vật chính</Label>
                <Input 
                  id="mainChar" 
                  placeholder="VD: Tô Minh, Dương Khai..." 
                  value={scriptContext.mainCharacter}
                  onChange={(e) => setScriptContext({ mainCharacter: e.target.value })}
                  className="bg-white/5 border-white/10 h-12 rounded-xl"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="summary">Bối cảnh tóm tắt (Tùy chọn)</Label>
                <Textarea 
                  id="summary" 
                  placeholder="VD: Sau khi đột phá cảnh giới, Tô Minh đang tìm cách trả thù..." 
                  value={scriptContext.summary}
                  onChange={(e) => setScriptContext({ summary: e.target.value })}
                  className="bg-white/5 border-white/10 min-h-[120px] rounded-xl"
                />
              </div>
            </div>

            <Button 
              size="lg" 
              onClick={generateScript} 
              disabled={isLoading || !scriptContext.mangaName || !scriptContext.mainCharacter}
              className="w-full bg-primary text-white rounded-2xl h-14 text-lg font-bold shadow-xl shadow-primary/20 active:scale-[0.98] transition-all group mt-4"
            >
              {isLoading ? "Đang phân tích..." : "Tự động viết kịch bản"}
              <Wand2 className="w-5 h-5 ml-2 group-hover:rotate-12 transition-transform" />
            </Button>

            {error && (
              <div className="bg-destructive/10 text-destructive p-4 rounded-xl flex items-center gap-2 border border-destructive/20 text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </Card>

          <div className="flex flex-col items-center justify-center border border-dashed border-white/10 rounded-3xl bg-white/5 p-12 text-center space-y-6">
             <div className="p-8 rounded-full bg-primary/5">
                <Bot className="w-16 h-16 text-primary/40" />
             </div>
             <div className="space-y-2">
                <h3 className="text-xl font-semibold opacity-60">Sảnh chờ Kịch bản</h3>
                <p className="text-muted-foreground max-w-xs mx-auto">
                  Hãy điền bối cảnh bên trái để Gemini có thể hiểu và viết kịch bản chuyên nghiệp nhất cho {panels.length} panel bạn đã tách.
                </p>
             </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* UI Trick: Replacement Alert */}
          {unknownCharacters.length > 0 && (
            <div className="bg-primary/20 border border-primary/30 p-4 rounded-2xl flex flex-wrap items-center justify-between gap-4 animate-in slide-in-from-top-4">
              <div className="flex items-center gap-3">
                <Ghost className="w-5 h-5 text-primary" />
                <p className="text-sm font-medium">
                  Phát hiện nhân vật vô danh: <span className="font-bold text-primary">{unknownCharacters[0]}</span>
                </p>
              </div>
              <div className="flex gap-2 flex-1 max-w-md">
                <Input 
                  placeholder="Nhập tên thật..." 
                  value={replacementName}
                  onChange={(e) => setReplacementName(e.target.value)}
                  className="bg-background/50 border-white/10 h-9"
                  onKeyDown={(e) => e.key === 'Enter' && handleReplaceCharacter(unknownCharacters[0])}
                />
                <Button size="sm" onClick={() => handleReplaceCharacter(unknownCharacters[0])} className="bg-primary rounded-lg shrink-0">
                  Thay thế tất cả
                </Button>
              </div>
            </div>
          )}

          <ScrollArea className="h-[calc(100vh-280px)] rounded-3xl border border-white/5 bg-white/5 p-2 glass">
            <div className="space-y-4 p-4">
                {timeline.map((item, index) => {
                  const panel = panels.find(p => p.id === item.panelId);
                  return (
                    <Card key={item.panelId} className="flex flex-col md:flex-row gap-6 p-6 bg-background/40 hover:bg-background border-white/5 rounded-3xl overflow-hidden hover:border-primary/20 transition-all duration-300 group">
                      <div className="w-full md:w-56 aspect-[3/4] shrink-0 rounded-2xl overflow-hidden bg-black flex items-center justify-center border border-white/10 group-hover:border-primary/30 transition-colors">
                        <img 
                          src={panel?.thumbnail} 
                          alt={`Panel ${index + 1}`}
                          className="object-contain w-full h-full"
                        />
                      </div>
                      <div className="flex-1 space-y-4">
                        <div className="flex items-center justify-between">
                           <div className="flex items-center gap-2">
                             <span className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-xs ring-1 ring-primary/20">
                               {index + 1}
                             </span>
                             <h4 className="font-bold text-muted-foreground text-xs uppercase tracking-tighter">Mô tả bối cảnh</h4>
                           </div>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label className="text-[10px] uppercase text-muted-foreground flex items-center gap-1.5"><User className="w-3 h-3"/> Người nói</Label>
                            <Input 
                              value={item.scriptItem.speaker}
                              onChange={(e) => updateTimelineItem(index, { scriptItem: { ...item.scriptItem, speaker: e.target.value } })}
                              className="bg-white/5 border-white/5 focus-visible:ring-primary h-10 rounded-xl font-bold"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label className="text-[10px] uppercase text-muted-foreground flex items-center gap-1.5"><Music className="w-3 h-3"/> SFX / Âm thanh</Label>
                            <Input 
                              value={item.scriptItem.sfx}
                              onChange={(e) => updateTimelineItem(index, { scriptItem: { ...item.scriptItem, sfx: e.target.value } })}
                              className="bg-white/5 border-white/5 focus-visible:ring-primary h-10 rounded-xl"
                              placeholder="Kếch, Rầm, Ting..."
                            />
                          </div>
                        </div>

                        <div className="space-y-2">
                          <Label className="text-[10px] uppercase text-muted-foreground flex items-center gap-1.5"><Type className="w-3 h-3"/> Lời thoại / Dẫn truyện</Label>
                          <Textarea 
                            value={item.scriptItem.dialogue}
                            onChange={(e) => updateTimelineItem(index, { scriptItem: { ...item.scriptItem, dialogue: e.target.value } })}
                            className="min-h-[100px] resize-y bg-white/5 border-white/5 focus-visible:ring-primary text-base leading-relaxed rounded-2xl"
                            placeholder="Nhập nội dung lồng tiếng..."
                          />
                        </div>
                        
                        <div className="p-3 rounded-xl bg-white/5 border border-white/5">
                           <p className="text-[11px] text-muted-foreground leading-snug italic">
                             <span className="font-bold not-italic mr-1">AI View:</span>
                             {item.scriptItem.scene_description}
                           </p>
                        </div>
                      </div>
                    </Card>
                  );
                })}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}
