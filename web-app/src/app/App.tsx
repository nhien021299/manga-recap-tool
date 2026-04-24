import { useEffect } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import { AppLayout } from "@/app/layout/AppLayout";
import { ErrorBoundary } from "@/app/ErrorBoundary";
import { StepBenchmark } from "@/features/benchmark/components/StepBenchmark";
import { StepCharacters } from "@/features/characters/components/StepCharacters";
import { StepExtract } from "@/features/extract/components/StepExtract";
import { StepRender } from "@/features/render/components/StepRender";
import { StepScript } from "@/features/script/components/StepScript";
import { StepUpload } from "@/features/upload/components/StepUpload";
import { StepVoice } from "@/features/voice/components/StepVoice";
import { useRecapStore } from "@/shared/storage/useRecapStore";

function App() {
  const { currentStep, init } = useRecapStore();

  useEffect(() => {
    void init();
  }, [init]);

  const renderCurrentStep = () => {
    switch (currentStep) {
      case "upload":
        return <StepUpload />;
      case "extract":
        return <StepExtract />;
      case "characters":
        return <StepCharacters />;
      case "script":
        return <StepScript />;
      case "voice":
        return <StepVoice />;
      case "render":
        return <StepRender />;
      case "benchmark":
        return <StepBenchmark />;
      default:
        return (
          <div className="flex h-[60vh] flex-col items-center justify-center space-y-4 text-center">
            <div className="animate-pulse rounded-full bg-white/5 p-8">
              <div className="h-16 w-16 rounded-full bg-primary/20" />
            </div>
            <h2 className="text-2xl font-bold">Chức năng đang được xây dựng</h2>
            <p className="text-muted-foreground">
              Milestone này sẽ hoàn thiện trong phiên làm việc tiếp theo.
            </p>
          </div>
        );
    }
  };

  return (
    <ErrorBoundary>
      <TooltipProvider>
        <AppLayout>{renderCurrentStep()}</AppLayout>
      </TooltipProvider>
    </ErrorBoundary>
  );
}

export default App;
