import { useState } from "react";
import { Upload, X, FileImage, Loader2 } from "lucide-react";
import { useRecapStore } from "@/store/useRecapStore";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { imageToImageData } from "@/lib/utils/imageUtils";
import { buildVirtualStrip } from "@/lib/image/virtualStrip";
import { buildSceneSuggestions, type DetectedLocalRect, type ImageDetectionResult } from "@/lib/image/sceneDetection";

export function StepUpload() {
  const { setVirtualStrip, setScenes, setPanels, setTimeline, setCurrentStep, setIsLoading, isLoading, setProgress, progress } = useRecapStore();
  const [files, setFiles] = useState<File[]>([]);

  const runWorkerTask = <T,>(worker: Worker, type: string, payload: Record<string, unknown>) =>
    new Promise<T>((resolve, reject) => {
      const handleMessage = (event: MessageEvent) => {
        const message = event.data as { type?: string; payload?: T };
        if (message.type === "SUCCESS") {
          cleanup();
          resolve(message.payload as T);
          return;
        }
        cleanup();
        reject(new Error(`Worker task failed: ${type}`));
      };

      const handleError = (error: ErrorEvent) => {
        cleanup();
        reject(error.error ?? new Error(error.message));
      };

      const cleanup = () => {
        worker.removeEventListener("message", handleMessage);
        worker.removeEventListener("error", handleError);
      };

      worker.addEventListener("message", handleMessage);
      worker.addEventListener("error", handleError);
      worker.postMessage({ type, payload });
    });

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const processImages = async () => {
    if (files.length === 0) return;

    // Overwrite previous local working data only when user starts a new upload run.
    setScenes([]);
    setPanels([]);
    setTimeline([]);

    setIsLoading(true);
    setProgress(5);

    try {
      const { images: stripImages, totalHeight, stripWidth } = await buildVirtualStrip(files);
      setVirtualStrip(stripImages, totalHeight, stripWidth);
      setProgress(15);

      const worker = new Worker(new URL('../../workers/imageProcessor.worker.ts', import.meta.url), { type: 'module' });
      const detections: ImageDetectionResult[] = [];

      for (let i = 0; i < stripImages.length; i++) {
        const imgMeta = stripImages[i];
        const imageData = await imageToImageData(imgMeta.file);

        const localRects = await runWorkerTask<DetectedLocalRect[]>(
          worker,
          "EXTRACT_PANELS_ROW_SCAN",
          { imageData }
        );
        const safeBreaks = await runWorkerTask<number[]>(
          worker,
          "SCAN_SAFE_BREAKS",
          { imageData }
        );

        detections.push({
          image: imgMeta,
          rects: localRects,
          safeBreaks,
        });

        setProgress(15 + Math.round(((i + 1) / stripImages.length) * 65));
      }
      
      worker.terminate();
      const suggestedScenes = buildSceneSuggestions(detections, stripWidth);
      setProgress(88);
      setScenes(suggestedScenes);
      setCurrentStep('extract');
    } catch (error) {
      console.error("Error processing images:", error);
    } finally {
      setIsLoading(false);
      setProgress(100);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="space-y-2">
        <h2 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
          Tải lên Manga/Webtoon
        </h2>
        <p className="text-muted-foreground">Phần mềm sẽ tự động nhận diện và tách các khung hình (panels).</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Dropzone */}
        <div className="space-y-4">
          <label className={cn(
            "h-[300px] border-2 border-dashed border-white/10 rounded-3xl flex flex-col items-center justify-center bg-white/5 hover:bg-white/10 transition-all cursor-pointer group relative overflow-hidden",
            isLoading && "pointer-events-none opacity-50"
          )}>
            <input type="file" multiple accept="image/*" className="hidden" onChange={onFileChange} />
            <div className="p-6 rounded-full bg-primary/20 group-hover:scale-110 transition-all duration-500">
              {isLoading ? <Loader2 className="w-12 h-12 text-primary animate-spin" /> : <Upload className="w-12 h-12 text-primary" />}
            </div>
            <div className="text-center mt-4">
              <p className="text-lg font-medium">Nhấn để chọn hoặc kéo thả</p>
              <p className="text-sm text-muted-foreground mt-1">PNG, JPG hoặc WebP</p>
            </div>
            {isLoading && (
              <div className="absolute inset-0 bg-background/60 backdrop-blur-sm flex items-center justify-center p-12">
                <div className="w-full space-y-4">
                  <div className="flex justify-between text-sm">
                    <span>Đang xử lý hình ảnh...</span>
                    <span>{progress}%</span>
                  </div>
                  <Progress value={progress} className="h-2" />
                </div>
              </div>
            )}
          </label>

          {files.length > 0 && !isLoading && (
            <Button 
              size="lg" 
              className="w-full bg-primary text-primary-foreground rounded-2xl h-16 text-xl font-black uppercase tracking-tighter shadow-glow shadow-glow-hover active:scale-[0.98] transition-all hover:opacity-100 border-none btn-pop ring-2 ring-white/10"
              onClick={processImages}
            >
              Tiến hành tách Panel ({files.length} ảnh)
            </Button>
          )}
        </div>

        {/* File List */}
        <div className="glass rounded-3xl p-6 border-white/5 min-h-[300px]">
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4 flex items-center gap-2">
            <FileImage className="w-4 h-4" /> Danh sách tệp ({files.length})
          </h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
            {files.length === 0 ? (
              <div className="h-32 flex flex-col items-center justify-center text-muted-foreground border border-dashed border-white/5 rounded-2xl">
                <p className="text-sm italic">Chưa có tệp nào được chọn</p>
              </div>
            ) : (
              files.map((file, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors group">
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                      <FileImage className="w-5 h-5" />
                    </div>
                    <div className="overflow-hidden">
                      <p className="text-sm font-medium truncate">{file.name}</p>
                      <p className="text-[10px] text-muted-foreground uppercase">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => removeFile(i)}
                    className="p-2 rounded-lg hover:bg-destructive/10 hover:text-destructive transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
