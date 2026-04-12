import { useRecapStore } from "@/store/useRecapStore";
import { SettingsDialog } from "@/components/SettingsDialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Upload,
  Scissors,
  FileText,
  Mic2,
  Video,
  Sun
} from "lucide-react";
import type { Step } from "@/types";

const steps: { id: Step; label: string; icon: any }[] = [
  { id: 'upload', label: 'Tải lên', icon: Upload },
  { id: 'extract', label: 'Tách Panel', icon: Scissors },
  { id: 'script', label: 'Kịch bản', icon: FileText },
  { id: 'voice', label: 'Lồng tiếng', icon: Mic2 },
  { id: 'render', label: 'Xuất video', icon: Video },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { currentStep, setCurrentStep } = useRecapStore();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r border-white/5 flex flex-col glass z-10">
        <div className="p-6">
          <h1 className="text-xl font-bold bg-gradient-to-br from-primary to-accent bg-clip-text text-transparent italic">
            Manga Recap Studio
          </h1>
        </div>

        <nav className="flex-1 px-4 py-4 space-y-2">
          {steps.map((step) => {
            const Icon = step.icon;
            const isActive = currentStep === step.id;
            return (
              <button
                key={step.id}
                onClick={() => setCurrentStep(step.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-500 group relative overflow-hidden",
                  isActive
                    ? "bg-primary/20 text-white shadow-[0_4px_15px_rgba(var(--color-primary),0.3)]"
                    : "text-muted-foreground hover:bg-white/10 hover:text-white border border-transparent"
                )}
              >
                <div className={cn(
                  "p-2 rounded-lg transition-all duration-500 relative z-10",
                  isActive
                    ? "text-white scale-110"
                    : "bg-white/5 group-hover:bg-primary group-hover:text-white group-hover:scale-110"
                )}>
                  <Icon className="w-4 h-4" />
                </div>

                <span className={cn(
                  "font-bold text-sm transition-all duration-300 relative z-10 tracking-wide",
                  isActive ? "text-white" : "text-muted-foreground group-hover:text-white"
                )}>
                  {step.label}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-white/5 flex items-center justify-between">
          <SettingsDialog />
          <div className="flex gap-2">
            <Button variant="ghost" size="icon" className="rounded-full text-muted-foreground">
              <Sun className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative overflow-hidden">
        {/* Top Header/Progress */}
        <header className="h-16 border-b border-white/5 flex items-center px-8 justify-between glass">
          <div className="flex items-center gap-4 group">
            <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest group-hover:text-primary transition-colors">Tiến độ dự án</span>
            <div className="w-64 h-2.5 bg-white/5 rounded-full overflow-hidden p-[2px] border border-white/5 shadow-inner">
              <div
                className="h-full bg-gradient-to-r from-primary via-accent to-primary bg-[length:200%_100%] animate-shimmer rounded-full transition-all duration-700 ease-[cubic-bezier(0.34,1.56,0.64,1)] relative"
                style={{
                  width: `${(steps.findIndex(s => s.id === currentStep) + 1) / steps.length * 100}%`,
                  boxShadow: '0 0 15px rgba(var(--color-primary), 0.3)'
                }}
              >
                <div className="absolute inset-0 bg-white/20 animate-pulse opacity-30" />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Action buttons could go here */}
          </div>
        </header>

        {/* Dynamic Content */}
        <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <div className="max-w-6xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-700">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
