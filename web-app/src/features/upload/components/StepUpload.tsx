import { useMemo, useRef, useState } from "react";
import { FileImage, FolderOpen, Loader2, Upload, X } from "lucide-react";
import { useRecapStore } from "@/store/useRecapStore";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { blobToBase64, generateThumbnail, imageToImageData } from "@/lib/utils/imageUtils";
import { buildVirtualStrip } from "@/lib/image/virtualStrip";
import { buildSceneSuggestions, type DetectedLocalRect, type ImageDetectionResult } from "@/lib/image/sceneDetection";
import { STRIP_WIDTH, type Panel } from "@/types";

const fileNameCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });

const sortFiles = (inputFiles: File[]) =>
  [...inputFiles].sort((left, right) =>
    fileNameCollator.compare(left.webkitRelativePath || left.name, right.webkitRelativePath || right.name)
  );

export function StepUpload() {
  const {
    setVirtualStrip,
    setScenes,
    setPanels,
    setPanelUnderstandings,
    setPanelUnderstandingMeta,
    setStoryMemories,
    setTimeline,
    setScriptMeta,
    setCurrentStep,
    setIsLoading,
    isLoading,
    setProgress,
    progress,
  } = useRecapStore();
  const [files, setFiles] = useState<File[]>([]);
  const directoryInputRef = useRef<HTMLInputElement>(null);
  const fileCountLabel = useMemo(() => `${files.length} ảnh`, [files.length]);

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

  const resetDerivedState = () => {
    setScenes([]);
    setPanels([]);
    setPanelUnderstandings([]);
    setPanelUnderstandingMeta({ panelSignature: "", rawOutput: "" });
    setStoryMemories([]);
    setTimeline([]);
    setScriptMeta({ status: "idle", sourceUnits: [], rawOutput: "", pipeline: "backend-gemini-unified" });
  };

  const buildPanelsFromFiles = async (panelFiles: File[]): Promise<Panel[]> => {
    const sortedFiles = sortFiles(panelFiles);
    const importedPanels: Panel[] = [];

    for (let index = 0; index < sortedFiles.length; index += 1) {
      const file = sortedFiles[index];
      const bitmap = await createImageBitmap(file);
      const width = bitmap.width;
      const height = bitmap.height;
      bitmap.close();

      const [thumbnail, base64] = await Promise.all([generateThumbnail(file), blobToBase64(file)]);
      importedPanels.push({
        id: `imported-panel-${index + 1}-${file.name}`,
        blob: file,
        base64,
        thumbnail,
        width,
        height,
        order: index,
      });

      setProgress(5 + Math.round(((index + 1) / sortedFiles.length) * 95));
    }

    return importedPanels;
  };

  const importCroppedPanels = async (panelFiles: File[]) => {
    if (panelFiles.length === 0) return;

    resetDerivedState();
    setVirtualStrip([], 0, STRIP_WIDTH);
    setFiles(sortFiles(panelFiles));
    setIsLoading(true);
    setProgress(5);

    try {
      const importedPanels = await buildPanelsFromFiles(panelFiles);
      setPanels(importedPanels);
      setCurrentStep("script");
    } catch (error) {
      console.error("Error importing cropped panels:", error);
    } finally {
      setIsLoading(false);
      setProgress(100);
      if (directoryInputRef.current) {
        directoryInputRef.current.value = "";
      }
    }
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(sortFiles(Array.from(e.target.files)));
    }
  };

  const onFolderChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selectedFiles = sortFiles(Array.from(e.target.files));
    await importCroppedPanels(selectedFiles);
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const processImages = async () => {
    if (files.length === 0) return;

    resetDerivedState();
    setIsLoading(true);
    setProgress(5);

    try {
      const { images: stripImages, totalHeight, stripWidth } = await buildVirtualStrip(files);
      setVirtualStrip(stripImages, totalHeight, stripWidth);
      setProgress(15);

      const worker = new Worker(new URL("../../../workers/imageProcessor.worker.ts", import.meta.url), { type: "module" });
      const detections: ImageDetectionResult[] = [];

      for (let i = 0; i < stripImages.length; i += 1) {
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
      setCurrentStep("extract");
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
        <h2 className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
          Tải lên manga/webtoon
        </h2>
        <p className="text-muted-foreground">
          Upload chap gốc để tách panel, hoặc import thẳng thư mục panel đã crop để đi thẳng sang bước script.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div className="space-y-4">
          <label
            className={cn(
              "relative flex h-[300px] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-3xl border-2 border-dashed border-white/10 bg-white/5 transition-all hover:bg-white/10",
              isLoading && "pointer-events-none opacity-50"
            )}
          >
            <input type="file" multiple accept="image/*" className="hidden" onChange={onFileChange} />
            <div className="rounded-full bg-primary/20 p-6 transition-all duration-500 group-hover:scale-110">
              {isLoading ? (
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
              ) : (
                <Upload className="h-12 w-12 text-primary" />
              )}
            </div>
            <div className="mt-4 text-center">
              <p className="text-lg font-medium">Nhấn để chọn hoặc kéo thả chương gốc</p>
              <p className="mt-1 text-sm text-muted-foreground">PNG, JPG hoặc WebP</p>
            </div>
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-background/60 p-12 backdrop-blur-sm">
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

          <input
            ref={directoryInputRef}
            type="file"
            multiple
            accept="image/*"
            className="hidden"
            onChange={onFolderChange}
            {...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
          />

          <Button
            type="button"
            variant="outline"
            onClick={() => directoryInputRef.current?.click()}
            disabled={isLoading}
            className="h-12 w-full rounded-2xl border-white/15 bg-white/5 text-sm font-semibold text-white/85 hover:bg-white/10"
          >
            <FolderOpen className="mr-2 h-4 w-4" />
            Import folder ảnh crop và vào thẳng bước script
          </Button>

          {files.length > 0 && !isLoading && (
            <Button
              size="lg"
              className="btn-pop h-16 w-full rounded-2xl border-none bg-primary text-xl font-black uppercase tracking-tighter text-primary-foreground ring-2 ring-white/10 shadow-glow transition-all hover:opacity-100 active:scale-[0.98]"
              onClick={processImages}
            >
              Tiến hành tách panel ({fileCountLabel})
            </Button>
          )}
        </div>

        <div className="glass min-h-[300px] rounded-3xl border-white/5 p-6">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-medium uppercase tracking-wider text-muted-foreground">
            <FileImage className="h-4 w-4" /> Danh sách tệp ({fileCountLabel})
          </h3>
          <div className="custom-scrollbar max-h-[400px] space-y-2 overflow-y-auto pr-2">
            {files.length === 0 ? (
              <div className="flex h-32 flex-col items-center justify-center rounded-2xl border border-dashed border-white/5 text-muted-foreground">
                <p className="text-sm italic">Chưa có tệp nào được chọn</p>
              </div>
            ) : (
              files.map((file, index) => (
                <div
                  key={`${file.webkitRelativePath || file.name}-${index}`}
                  className="group flex items-center justify-between rounded-xl border border-white/5 bg-white/5 p-3 transition-colors hover:bg-white/10"
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <FileImage className="h-5 w-5" />
                    </div>
                    <div className="overflow-hidden">
                      <p className="truncate text-sm font-medium">{file.name}</p>
                      <p className="truncate text-[10px] uppercase text-muted-foreground">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                        {file.webkitRelativePath ? ` • ${file.webkitRelativePath}` : ""}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => removeFile(index)}
                    className="rounded-lg p-2 opacity-0 transition-colors hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                  >
                    <X className="h-4 w-4" />
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
