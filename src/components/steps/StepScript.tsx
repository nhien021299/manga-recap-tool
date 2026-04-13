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
  AlertCircle,
  Music,
  User,
  Mic,
  MessageSquareQuote,
  History,
  Ghost,
  Eye,
  Loader2,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { useState, useMemo } from "react";
import { GeminiLogs } from "@/components/GeminiLogs";

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
      const voiceMatch = item.scriptItem.voiceover_text?.match(/\[(.*?)\]/g);
      if (voiceMatch) {
        voiceMatch.forEach(m => found.add(m));
      }
    });
    return Array.from(found);
  }, [timeline]);

  const handleReplaceCharacter = (placeholder: string) => {
    if (!replacementName) return;
    
    const newTimeline = timeline.map(item => ({
      ...item,
      scriptItem: {
        ...item.scriptItem,
        voiceover_text: item.scriptItem.voiceover_text?.replace(
          new RegExp(placeholder.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&'), 'g'), 
          replacementName
        ) || ''
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
          <h2 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">
            Kịch bản Recap
          </h2>
          <p className="text-white/70">AI viết kịch bản dựa trên diễn biến hình ảnh. Có thể chỉnh sửa thủ công.</p>
        </div>
        <div className="flex gap-3">
          <Button 
            variant="outline" 
            onClick={prevStep} 
            className="rounded-xl border-white/30 bg-white/10 text-white hover:bg-white/20 transition-all font-bold px-6 shadow-sm ring-1 ring-white/10"
          >
            <ChevronLeft className="w-4 h-4 mr-2" /> Quay lại
          </Button>
          <Button 
            onClick={nextStep} 
            disabled={timeline.length === 0} 
            className="bg-primary text-primary-foreground hover:opacity-90 rounded-xl shadow-glow shadow-glow-hover btn-pop transition-all font-black uppercase tracking-tight px-8"
          >
            Tiếp tục <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>

      {timeline.length === 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">
          {/* Step 1: Global Context Form */}
          <Card className="p-8 bg-white/5 border-white/10 rounded-3xl space-y-6 glass shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/30 ring-1 ring-primary/50">
                <History className="w-5 h-5 text-white" />
              </div>
              <h3 className="text-xl font-bold text-white">Thiết lập Bối cảnh</h3>
            </div>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="mangaName" className="text-white/80 font-semibold tracking-wide uppercase text-[10px]">Tên truyện</Label>
                <Input 
                  id="mangaName" 
                  placeholder="VD: Cầu Ma, Võ Luyện Đỉnh Phong..." 
                  value={scriptContext.mangaName}
                  onChange={(e) => setScriptContext({ mangaName: e.target.value })}
                  className="bg-white/10 border-white/20 h-12 rounded-xl text-white placeholder:text-white/30 focus:border-primary/50"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="mainChar" className="text-white/80 font-semibold tracking-wide uppercase text-[10px]">Nhân vật chính</Label>
                <Input 
                  id="mainChar" 
                  placeholder="VD: Tô Minh, Dương Khai..." 
                  value={scriptContext.mainCharacter}
                  onChange={(e) => setScriptContext({ mainCharacter: e.target.value })}
                  className="bg-white/10 border-white/20 h-12 rounded-xl text-white placeholder:text-white/30 focus:border-primary/50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="summary" className="text-white/80 font-semibold tracking-wide uppercase text-[10px]">Bối cảnh tóm tắt (Tùy chọn)</Label>
                <Textarea 
                  id="summary" 
                  placeholder="VD: Sau khi đột phá cảnh giới, Tô Minh đang tìm cách trả thù..." 
                  value={scriptContext.summary}
                  onChange={(e) => setScriptContext({ summary: e.target.value })}
                  className="bg-white/10 border-white/20 min-h-[120px] rounded-xl text-white placeholder:text-white/30 focus:border-primary/50"
                />
              </div>
            </div>

            <Button 
              size="lg" 
              onClick={generateScript} 
              disabled={isLoading || !scriptContext.mangaName || !scriptContext.mainCharacter}
              className="w-full bg-primary text-primary-foreground rounded-2xl h-16 text-xl font-black uppercase tracking-tighter shadow-glow shadow-glow-hover btn-pop active:scale-[0.98] transition-all group mt-4 hover:opacity-100 ring-2 ring-white/10"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin text-white" />
                  Đang phân tích...
                </>
              ) : (
                <>
                  Tự động viết kịch bản
                  <Wand2 className="w-5 h-5 ml-2 group-hover:rotate-12 transition-transform" />
                </>
              )}
            </Button>

            {error && (
              <div className="bg-destructive/20 text-white p-4 rounded-xl flex items-center gap-2 border border-destructive/30 text-sm shadow-inner">
                <AlertCircle className="w-4 h-4 shrink-0 text-[#ff4d4d]" />
                <span>{error}</span>
              </div>
            )}
          </Card>

          <Card className="flex flex-col border border-white/10 rounded-3xl bg-white/5 p-6 glass shadow-xl">
            <GeminiLogs />
          </Card>
        </div>
      ) : (
        <div className="space-y-6 pb-20">
          {/* UI Trick: Replacement Alert */}
          {unknownCharacters.length > 0 && (
            <div className="bg-primary/30 border border-primary/50 p-4 rounded-2xl flex flex-wrap items-center justify-between gap-4 animate-in slide-in-from-top-4 shadow-lg ring-1 ring-primary/20">
              <div className="flex items-center gap-3">
                <Ghost className="w-5 h-5 text-white" />
                <p className="text-sm font-bold text-white">
                  Phát hiện nhân vật vô danh: <span className="font-bold text-white bg-primary/40 px-2 py-0.5 rounded-lg">{unknownCharacters[0]}</span>
                </p>
              </div>
              <div className="flex gap-2 flex-1 max-w-md">
                <Input 
                  placeholder="Nhập tên thật..." 
                  value={replacementName}
                  onChange={(e) => setReplacementName(e.target.value)}
                  className="bg-black/40 border-white/20 h-9 text-white placeholder:text-white/30"
                  onKeyDown={(e) => e.key === 'Enter' && handleReplaceCharacter(unknownCharacters[0])}
                />
                <Button size="sm" onClick={() => handleReplaceCharacter(unknownCharacters[0])} className="bg-primary text-primary-foreground hover:opacity-90 font-bold rounded-lg shrink-0 shadow-glow shadow-glow-hover px-4">
                  Thay thế
                </Button>
              </div>
            </div>
          )}

          <ScrollArea className="h-[calc(100vh-220px)] rounded-3xl border border-white/10 bg-white/5 p-2 glass">
            <div className="space-y-4 p-4">
                {timeline.map((item, index) => {
                  const panel = panels.find(p => p.id === item.panelId);
                  return (
                    <Card key={item.panelId} className="flex flex-col md:flex-row gap-6 p-6 bg-white/5 hover:bg-white/10 border-white/10 rounded-3xl overflow-hidden hover:border-primary/40 transition-all duration-300 group shadow-lg">
                      <div className="w-full md:w-56 aspect-[3/4] shrink-0 rounded-2xl overflow-hidden bg-black flex items-center justify-center border border-white/10 group-hover:border-primary/40 transition-colors shadow-2xl">
                        <img 
                          src={panel?.thumbnail} 
                          alt={`Panel ${index + 1}`}
                          className="object-contain w-full h-full"
                        />
                      </div>
                      <div className="flex-1 space-y-4">
                        <div className="flex items-center justify-between">
                           <div className="flex items-center gap-2">
                             <span className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-white font-bold text-xs ring-1 ring-primary/50 shadow-[0_0_10px_rgba(var(--color-primary),0.3)]">
                               {index + 1}
                             </span>
                             <h4 className="font-extrabold text-white/90 text-[10px] uppercase tracking-wider">Cảnh #{index + 1}</h4>
                           </div>
                        </div>
                        
                        {/* MAIN: Kịch Bản Đọc (voiceover_text) */}
                        <div className="space-y-2">
                          <Label className="text-[10px] uppercase text-white/60 font-bold flex items-center gap-1.5 tracking-widest"><Mic className="w-3 h-3 text-primary"/> Kịch Bản Đọc</Label>
                          <Textarea 
                            value={item.scriptItem.voiceover_text || ""}
                            onChange={(e) => updateTimelineItem(index, { scriptItem: { ...item.scriptItem, voiceover_text: e.target.value } })}
                            className="min-h-[120px] resize-y bg-primary/10 border-primary/20 focus-visible:ring-primary text-white text-base leading-relaxed rounded-2xl font-medium shadow-inner p-4"
                            placeholder="Kịch bản dẫn truyện đã bao gồm lời thoại..."
                          />
                        </div>

                        {/* FOOTER: AI View + SFX Tags */}
                        <div className="flex flex-col xl:flex-row items-start gap-4">
                          <div className="w-full xl:flex-1 p-3 rounded-xl bg-white/5 border border-white/10 shadow-inner min-h-[60px]">
                             <p className="text-[11px] text-white/80 leading-snug italic font-medium">
                               <span className="font-extrabold not-italic mr-1 inline-flex items-center gap-1 text-primary uppercase text-[9px]"><Eye className="w-3 h-3 inline" /> AI View:</span>
                               {item.scriptItem.ai_view}
                             </p>
                          </div>
                          
                          <div className="w-full xl:w-72 space-y-2 shrink-0">
                            <Label className="text-[10px] uppercase text-white/60 font-bold flex items-center gap-1.5 tracking-widest"><Music className="w-3 h-3 text-primary"/> Hiệu ứng âm thanh (SFX)</Label>
                            <div className="flex flex-wrap gap-2 items-center p-2 rounded-xl bg-black/40 border border-white/10 min-h-[60px]">
                              {(item.scriptItem.sfx || []).map((sfxItem, sfxIdx) => (
                                <span key={sfxIdx} className="text-[11px] px-2.5 py-1 rounded-lg bg-amber-500/20 text-white font-medium border border-amber-500/30 flex items-center gap-1 shadow-sm">
                                  {sfxItem}
                                  <button 
                                    className="ml-1 text-white/50 hover:text-white"
                                    onClick={() => {
                                      const newSfx = [...(item.scriptItem.sfx || [])];
                                      newSfx.splice(sfxIdx, 1);
                                      updateTimelineItem(index, { scriptItem: { ...item.scriptItem, sfx: newSfx } });
                                    }}
                                  >
                                    ×
                                  </button>
                                </span>
                              ))}
                              
                              <Input 
                                className="h-7 w-28 text-[11px] bg-transparent border-dashed border-white/20 text-white placeholder:text-white/30 rounded-lg px-2 focus-visible:ring-1 focus-visible:ring-amber-500/50"
                                placeholder="+ Thêm tag"
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    const val = e.currentTarget.value.trim();
                                    if (val) {
                                      const newSfx = [...(item.scriptItem.sfx || []), val];
                                      updateTimelineItem(index, { scriptItem: { ...item.scriptItem, sfx: newSfx } });
                                      e.currentTarget.value = '';
                                    }
                                  }
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}

                {/* Log section at the bottom for scrollable content */}
                <Card className="mt-8 p-6 bg-white/5 border-white/10 rounded-3xl glass">
                  <GeminiLogs />
                </Card>
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}
