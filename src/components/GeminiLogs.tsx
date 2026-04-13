import { useRecapStore } from "@/store/useRecapStore";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { Terminal, Trash2 } from "lucide-react";
import { useEffect, useRef } from "react";

export function GeminiLogs() {
  const { logs, clearLogs } = useRecapStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom since newest is at the bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  if (logs.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-50 space-y-4">
        <Terminal className="w-12 h-12" />
        <p className="text-sm font-medium uppercase tracking-widest text-white">Sẵn sàng nhận Log từ Gemini</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[600px] space-y-4">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Gemini Session Logs</h3>
        </div>
        <button 
          onClick={clearLogs}
          className="p-1.5 rounded-lg hover:bg-white/10 text-white/50 hover:text-white transition-colors"
          title="Xóa log"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <div 
        className="flex-1 rounded-2xl bg-black/40 border border-white/10 p-4 font-mono text-[11px] leading-relaxed overflow-y-auto custom-scrollbar"
        style={{ scrollBehavior: 'smooth' }}
      >
        <div className="space-y-6">
          {logs.map((log) => (
            <div key={log.id} className="space-y-2 animate-in fade-in slide-in-from-left-2 duration-300">
              <div className="flex items-start gap-2">
                <span className="text-white/40 shrink-0 select-none">[{log.timestamp}]</span>
                <span className={cn(
                  "font-bold uppercase shrink-0 select-none",
                  log.type === 'request' && "text-white",
                  log.type === 'result' && "text-[#00ff9f]", // Neon green
                  log.type === 'error' && "text-[#ff4d4d]"    // Red
                )}>
                  {log.type}:
                </span>
                <span className="flex-1 break-words text-white font-medium">{log.message}</span>
              </div>
              
              {log.details && (
                <div className="mt-2 bg-white/5 text-white/80 overflow-x-auto border border-white/10 rounded-lg custom-scrollbar">
                  <pre className="p-3 text-[10px] break-all whitespace-pre-wrap font-mono">
                    <code className="text-white/90">{log.details}</code>
                  </pre>
                </div>
              )}
            </div>
          ))}
          <div ref={scrollRef} className="h-1" />
        </div>
      </div>
    </div>
  );
}
