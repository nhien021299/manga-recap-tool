import {
  BarChart3,
  FileText,
  Mic2,
  Scissors,
  Sun,
  type LucideIcon,
  Upload,
  Video,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { SettingsDialog } from "@/shared/components/SettingsDialog";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { Step } from "@/shared/types";

const steps: Array<{ id: Step; label: string; icon: LucideIcon }> = [
  { id: "upload", label: "Tải Lên", icon: Upload },
  { id: "extract", label: "Tách Panel", icon: Scissors },
  { id: "script", label: "Kịch Bản", icon: FileText },
  { id: "voice", label: "Lồng Tiếng", icon: Mic2 },
  { id: "render", label: "Xuất Video", icon: Video },
  { id: "benchmark", label: "Benchmark", icon: BarChart3 },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { currentStep, setCurrentStep } = useRecapStore();
  const currentIndex = Math.max(steps.findIndex((step) => step.id === currentStep), 0);
  const progress = `${((currentIndex + 1) / steps.length) * 100}%`;

  return (
    <div className="editor-shell flex h-screen w-full overflow-hidden text-foreground">
      <aside className="surface-panel z-10 flex w-56 flex-col border-r border-sidebar-border bg-sidebar/92">
        <div className="border-b border-sidebar-border px-5 py-4">
          <p className="mb-1 text-[14px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Manga Recap
          </p>
          <h1 className="text-base font-semibold tracking-tight text-foreground">Midnight Studio</h1>
        </div>

        <nav className="flex-1 space-y-1.5 px-3 py-4">
          {steps.map((step) => {
            const Icon = step.icon;
            const isActive = currentStep === step.id;

            return (
              <button
                key={step.id}
                onClick={() => setCurrentStep(step.id)}
                className={cn(
                  "group relative flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors duration-200",
                  isActive
                    ? "border-accent/25 bg-accent/12 text-foreground"
                    : "border-transparent text-muted-foreground hover:border-border hover:bg-muted/55 hover:text-foreground"
                )}
              >
                <div
                  className={cn(
                    "relative z-10 rounded-md border p-1.5 transition-colors duration-200",
                    isActive
                      ? "border-accent/25 bg-accent/15 text-accent"
                      : "border-border bg-muted/50 text-muted-foreground group-hover:text-foreground"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>

                <span
                  className={cn(
                    "relative z-10 text-sm font-medium tracking-[0.01em] transition-colors duration-200",
                    isActive ? "text-foreground" : "text-muted-foreground group-hover:text-foreground"
                  )}
                >
                  {step.label}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="flex items-center justify-between border-t border-sidebar-border px-3 py-3">
          <SettingsDialog />
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-md text-muted-foreground">
            <Sun className="h-3.5 w-3.5" />
          </Button>
        </div>
      </aside>

      <main className="relative flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center justify-between border-b border-border/80 bg-background/90 px-6 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <span className="text-[10px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
              Tiến độ dự án
            </span>
            <div className="h-2 w-52 overflow-hidden rounded-full border border-border bg-muted/65 p-[1px]">
              <div className="h-full rounded-full bg-accent transition-all duration-500 ease-out" style={{ width: progress }} />
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            {currentIndex + 1}/{steps.length}
          </div>
        </header>

        <div className="custom-scrollbar flex-1 overflow-y-auto px-4 py-4 md:px-6 md:py-5">
          <div className="mx-auto max-w-full animate-in fade-in slide-in-from-bottom-2 duration-500">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
