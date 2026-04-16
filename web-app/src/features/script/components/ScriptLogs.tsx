import { useEffect, useRef } from "react";
import { CheckCircle2, Loader2, Terminal, Trash2, XCircle } from "lucide-react";

import { useRecapStore } from "@/shared/storage/useRecapStore";

const formatTimestamp = (value: string) => {
  const parsedDate = new Date(value);
  if (!Number.isNaN(parsedDate.getTime())) {
    return parsedDate.toLocaleTimeString();
  }
  return value;
};

export function ScriptLogs() {
  const { logs, clearLogs, isLoading } = useRecapStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  if (logs.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center space-y-4 text-muted-foreground opacity-50">
        <Terminal className="h-12 w-12" />
        <p className="text-sm font-medium uppercase tracking-widest text-white">No generation logs yet</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex shrink-0 items-center justify-between border-b border-white/10 pb-4">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/20 p-2 ring-1 ring-primary/50">
            <Terminal className="h-4 w-4 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-black uppercase tracking-widest text-white">Backend Gemini Log</h3>
            <p className="mt-0.5 text-xs text-white/50">
              Stage 1 builds panel understanding. Stage 2 writes narration on the backend.
            </p>
          </div>
        </div>
        <button
          onClick={clearLogs}
          className="rounded-xl border border-red-500/30 bg-red-500/10 p-2.5 text-red-200 shadow-sm transition-all hover:bg-red-500/20"
          title="Clear generation logs"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      <div className="max-h-[750px] space-y-3 overflow-y-auto pr-2">
        {logs.map((log) => (
          <div
            key={log.id}
            className="rounded-2xl border border-white/10 bg-black/20 p-4 shadow-inner transition-colors hover:border-white/15"
          >
            <div className="flex items-start gap-3">
              {log.type === "request" && (
                isLoading ? <Loader2 className="mt-0.5 h-4 w-4 animate-spin text-primary" /> : <Terminal className="mt-0.5 h-4 w-4 text-primary" />
              )}
              {log.type === "result" && <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />}
              {log.type === "error" && <XCircle className="mt-0.5 h-4 w-4 text-red-500" />}

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-[0.24em] text-white/40">
                    {log.type}
                  </span>
                  <span className="text-[10px] text-white/30">{formatTimestamp(log.timestamp)}</span>
                </div>
                <p className="mt-1 break-words text-sm font-medium text-white/85">{log.message}</p>
                {log.details && (
                  <div className="custom-scrollbar mt-3 overflow-x-auto rounded-xl border border-white/10 bg-white/5">
                    <pre className="whitespace-pre-wrap break-all p-3 text-[11px] leading-relaxed text-white/65">
                      {log.details}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={scrollRef} className="h-2" />
      </div>
    </div>
  );
}
