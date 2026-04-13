import { useRecapStore } from "@/store/useRecapStore";
import { useVoiceGeneration } from "@/hooks/useVoiceGeneration";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  ChevronRight, 
  ChevronLeft, 
  Volume2, 
  RefreshCw,
  Play,
  Pause,
  AlertCircle,
  Clock
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useState, useRef } from "react";

export function StepVoice() {
  const { timeline, panels, setCurrentStep, isLoading, progress } = useRecapStore();
  const { generateAllVoices, generateSingleVoice, error } = useVoiceGeneration();
  const [playingIdx, setPlayingIdx] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const nextStep = () => setCurrentStep('render');
  const prevStep = () => setCurrentStep('script');

  const togglePlay = (index: number, url: string) => {
    if (playingIdx === index) {
      audioRef.current?.pause();
      setPlayingIdx(null);
    } else {
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
        setPlayingIdx(index);
        audioRef.current.onended = () => setPlayingIdx(null);
      }
    }
  };

  const totalDuration = timeline.reduce((acc, item) => acc + (item.audioDuration || 0), 0);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <audio ref={audioRef} className="hidden" />

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
            Lồng tiếng AI
          </h2>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
             <p>Sử dụng ElevenLabs để tạo giọng đọc tự nhiên.</p>
             {totalDuration > 0 && (
               <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-primary/10 text-primary font-medium border border-primary/20">
                 <Clock className="w-3.5 h-3.5" />
                 Tổng cộng: {totalDuration.toFixed(1)}s
               </div>
             )}
          </div>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={prevStep} className="rounded-xl border-white/10">
            <ChevronLeft className="w-4 h-4 mr-2" /> Quay lại
          </Button>
          <Button onClick={nextStep} disabled={totalDuration === 0} className="bg-primary text-primary-foreground hover:opacity-90 rounded-xl shadow-glow shadow-glow-hover transition-all font-bold">
            Tiếp tục bước Cuối <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>

      {!timeline.some(item => item.audioUrl) ? (
        <div className="h-[400px] flex flex-col items-center justify-center border border-dashed border-white/10 rounded-3xl bg-white/5 space-y-6">
          <div className="p-8 rounded-full bg-primary/10">
            <Volume2 className="w-16 h-16 text-primary" />
          </div>
          <div className="text-center space-y-2">
            <h3 className="text-xl font-semibold">Tạo âm thanh Thuyết minh</h3>
            <p className="text-muted-foreground max-w-sm px-4">
              Biến kịch bản thành giọng nói thật với công nghệ ElevenLabs Multi-lingual v2.
            </p>
          </div>

          {error && (
            <div className="bg-destructive/10 text-destructive px-4 py-2 rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm font-medium">{error}</span>
            </div>
          )}

          <div className="w-full max-w-xs space-y-4">
            <Button 
              size="lg" 
              onClick={generateAllVoices} 
              disabled={isLoading}
              className="w-full bg-primary text-primary-foreground rounded-2xl h-14 text-lg font-bold shadow-glow shadow-glow-hover active:scale-[0.98] transition-all hover:opacity-90 border-none"
            >
              {isLoading ? "Đang tạo Audio..." : "Bắt đầu tạo tất cả thoại"}
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
        <ScrollArea className="h-[calc(100vh-220px)] rounded-3xl border border-white/5 bg-white/5 p-2 glass">
           <div className="space-y-3 p-4">
              {timeline.map((item, index) => {
                const panel = panels.find(p => p.id === item.panelId);
                return (
                  <Card key={item.panelId} className="flex items-center gap-4 p-3 bg-background border-white/5 rounded-2xl hover:border-primary/20 transition-all group">
                    <div className="w-20 h-20 shrink-0 rounded-xl overflow-hidden bg-black border border-white/5">
                      <img src={panel?.thumbnail} className="w-full h-full object-cover" />
                    </div>
                    
                    <div className="flex-1 space-y-1">
                      <p className="text-sm font-medium line-clamp-2 leading-relaxed italic text-muted-foreground">
                        "{item.scriptItem.voiceover_text}"
                      </p>
                      <div className="flex items-center gap-3">
                         {item.audioUrl ? (
                            <Button 
                              size="sm" 
                              variant="secondary" 
                              className="h-8 rounded-full bg-white/5 hover:bg-white/10 border-white/10"
                              onClick={() => togglePlay(index, item.audioUrl!)}
                            >
                              {playingIdx === index ? (
                                <><Pause className="w-3 h-3 mr-2" /> Dừng</>
                              ) : (
                                <><Play className="w-3 h-3 mr-2" /> Nghe thử</>
                              )}
                            </Button>
                         ) : (
                            <span className="text-[10px] text-destructive flex items-center gap-1">
                               <AlertCircle className="w-3 h-3" /> Chưa có âm thanh
                            </span>
                         )}
                         <span className="text-[10px] text-muted-foreground uppercase font-mono">
                            {item.audioDuration ? `${item.audioDuration.toFixed(1)}s` : '--'}
                         </span>
                      </div>
                    </div>

                    <Button 
                      size="icon" 
                      variant="ghost" 
                      onClick={() => generateSingleVoice(index)}
                      className="rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                       <RefreshCw className="w-4 h-4" />
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
