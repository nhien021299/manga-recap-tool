import { AppLayout } from "@/components/layout/AppLayout";
import { useRecapStore } from "@/store/useRecapStore";
import { TooltipProvider } from "@/components/ui/tooltip";
import { StepUpload } from "@/components/steps/StepUpload";
import { StepExtract } from "@/components/steps/StepExtract";
import { StepScript } from "@/components/steps/StepScript";
import { StepVoice } from "@/components/steps/StepVoice";

import { useEffect } from "react";

function App() {
  const { currentStep } = useRecapStore();

  const renderCurrentStep = () => {
    switch (currentStep) {
      case 'upload': return <StepUpload />;
      case 'extract': return <StepExtract />;
      case 'script': return <StepScript />;
      case 'voice': return <StepVoice />;
      default: return (
        <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-4">
          <div className="p-8 rounded-full bg-white/5 animate-pulse">
            <div className="w-16 h-16 bg-primary/20 rounded-full" />
          </div>
          <h2 className="text-2xl font-bold">Chức năng đang được xây dựng</h2>
          <p className="text-muted-foreground">Milestone này sẽ hoàn thiện trong phiên làm việc tiếp theo.</p>
        </div>
      );
    }
  };

  return (
    <TooltipProvider>
      <AppLayout>
        {renderCurrentStep()}
      </AppLayout>
    </TooltipProvider>
  );
}

export default App;
