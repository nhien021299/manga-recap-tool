import { useEffect, useRef } from "react";
import { Terminal, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useRecapStore } from "@/shared/storage/useRecapStore";

export function ScriptLogs() {
  const { logs, clearLogs } = useRecapStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  if (logs.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center space-y-4 text-muted-foreground opacity-50">
        <Terminal className="h-12 w-12" />
        <p className="text-sm font-medium uppercase tracking-widest text-white">
          Ready to receive backend job logs
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-[600px] flex-col space-y-4">
      <div className="flex shrink-0 items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-white">Backend Job Logs</h3>
        </div>
        <button
          onClick={clearLogs}
          className="rounded-lg p-1.5 text-white/50 transition-colors hover:bg-white/10 hover:text-white"
          title="Clear logs"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      <div
        className="custom-scrollbar flex-1 overflow-y-auto rounded-2xl border border-white/10 bg-black/40 p-4 font-mono text-[11px] leading-relaxed"
        style={{ scrollBehavior: "smooth" }}
      >
        <div className="space-y-6">
          {logs.map((log) => (
            <div key={log.id} className="animate-in fade-in slide-in-from-left-2 space-y-2 duration-300">
              <div className="flex items-start gap-2">
                <span className="shrink-0 select-none text-white/40">[{log.timestamp}]</span>
                <span
                  className={cn(
                    "shrink-0 select-none font-bold uppercase",
                    log.type === "request" && "text-white",
                    log.type === "result" && "text-[#00ff9f]",
                    log.type === "error" && "text-[#ff4d4d]"
                  )}
                >
                  {log.type}:
                </span>
                <span className="flex-1 break-words font-medium text-white">{log.message}</span>
              </div>

              {log.details && (
                <div className="custom-scrollbar mt-2 overflow-x-auto rounded-lg border border-white/10 bg-white/5 text-white/80">
                  <pre className="break-all whitespace-pre-wrap p-3 font-mono text-[10px]">
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
