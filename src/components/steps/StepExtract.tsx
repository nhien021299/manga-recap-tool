import { useRecapStore } from "@/store/useRecapStore";
import { Button } from "@/components/ui/button";
import {
  Plus,
  Trash2,
  ChevronRight,
  ChevronLeft,
  LayoutGrid,
  Maximize2,
  X,
  Loader2
} from "lucide-react";
import {
  Card,
  CardContent
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { useState, useEffect, useRef } from "react";
import ReactCrop, { type Crop } from 'react-image-crop';
import 'react-image-crop/dist/ReactCrop.css';
import { cropImage, generateThumbnail, blobToBase64 } from "@/lib/utils/imageUtils";

export function StepExtract() {
  const { panels, setPanels, setCurrentStep } = useRecapStore();
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Crop state
  const [isEditingCrop, setIsEditingCrop] = useState(true); // Default to true as requested
  const [crop, setCrop] = useState<Crop>();
  const [isSavingCrop, setIsSavingCrop] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // Sync crop grid when panel selection changes - Only run when index changes to avoid lag
  useEffect(() => {
    if (selectedIdx !== null && imgRef.current) {
      const p = panels[selectedIdx];
      const img = imgRef.current;
      if (p.rect && img.naturalWidth > 0) {
        setCrop({
          unit: '%',
          x: (p.rect.x / img.naturalWidth) * 100,
          y: (p.rect.y / img.naturalHeight) * 100,
          width: (p.rect.width / img.naturalWidth) * 100,
          height: (p.rect.height / img.naturalHeight) * 100,
        });
      }
    }
  }, [selectedIdx]); // Removed panels dependency to prevent jitter during updates

  // When opening a panel, default to editing mode
  const openPanelDetail = (idx: number) => {
    setSelectedIdx(idx);
    setIsEditingCrop(true);
    // Grid cleanup will happen via the 'key' on ReactCrop
  };

  const removePanel = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setPanels(panels.filter(p => p.id !== id));

    const newSelected = new Set(selectedIds);
    newSelected.delete(id);
    setSelectedIds(newSelected);

    if (selectedIdx !== null && panels[selectedIdx]?.id === id) {
      setSelectedIdx(null);
    }
  };

  const deleteSelected = () => {
    setPanels(panels.filter(p => !selectedIds.has(p.id)));
    setSelectedIds(new Set());
    setSelectedIdx(null);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === panels.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(panels.map(p => p.id)));
    }
  };

  const toggleSelect = (e: React.MouseEvent | React.ChangeEvent, id: string) => {
    e.stopPropagation();
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const nextStep = () => setCurrentStep('script');
  const prevStep = () => setCurrentStep('upload');

  const goToNext = () => {
    if (selectedIdx !== null && selectedIdx < panels.length - 1) {
      setSelectedIdx(selectedIdx + 1);
    }
  };

  const goToPrev = () => {
    if (selectedIdx !== null && selectedIdx > 0) {
      setSelectedIdx(selectedIdx - 1);
    }
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (selectedIdx === null || isEditingCrop) return;
      if (e.key === "ArrowRight") goToNext();
      if (e.key === "ArrowLeft") goToPrev();
      if (e.key === "Escape") setSelectedIdx(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedIdx, panels.length, isEditingCrop]);

  const onImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    imgRef.current = img;
    if (selectedIdx !== null) {
      const p = panels[selectedIdx];
      if (p.rect) {
        setCrop({
          unit: '%',
          x: (p.rect.x / img.naturalWidth) * 100,
          y: (p.rect.y / img.naturalHeight) * 100,
          width: (p.rect.width / img.naturalWidth) * 100,
          height: (p.rect.height / img.naturalHeight) * 100,
        });
      }
    }
  };

  const saveEditedCrop = async (currentCrop: Crop) => {
    if (selectedIdx === null || !currentCrop || !imgRef.current) return;
    const p = panels[selectedIdx];
    if (!p.originalImageRef) return;

    setIsSavingCrop(true);
    try {
      const img = imgRef.current;
      let pixelCrop = { x: 0, y: 0, width: 0, height: 0 };

      if (currentCrop.unit === '%') {
        pixelCrop = {
          x: Math.round((currentCrop.x / 100) * img.naturalWidth),
          y: Math.round((currentCrop.y / 100) * img.naturalHeight),
          width: Math.round((currentCrop.width / 100) * img.naturalWidth),
          height: Math.round((currentCrop.height / 100) * img.naturalHeight),
        };
      } else {
        const scaleX = img.naturalWidth / img.width;
        const scaleY = img.naturalHeight / img.height;
        pixelCrop = {
          x: Math.round(currentCrop.x * scaleX),
          y: Math.round(currentCrop.y * scaleY),
          width: Math.round(currentCrop.width * scaleX),
          height: Math.round(currentCrop.height * scaleY),
        };
      }

      if (pixelCrop.width <= 0 || pixelCrop.height <= 0) return;

      const response = await fetch(p.originalImageRef);
      if (!response.ok) throw new Error("Fetch failed");
      const originalBlob = await response.blob();

      const newPanelBlob = await cropImage(originalBlob, pixelCrop);
      const newThumbnail = await generateThumbnail(newPanelBlob);
      const newBase64 = await blobToBase64(newPanelBlob);

      setPanels(panels.map((pnl, i) => i === selectedIdx ? {
        ...pnl,
        rect: pixelCrop,
        blob: newPanelBlob,
        base64: newBase64,
        thumbnail: newThumbnail,
        width: pixelCrop.width,
        height: pixelCrop.height
      } : pnl));
    } catch (err: any) {
      console.error("Auto-save error:", err);
    } finally {
      setIsSavingCrop(false);
    }
  };

  // Close lightbox helper
  const closeLightbox = () => {
    if (!isEditingCrop) {
      setSelectedIdx(null);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header Section */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
            Kiểm tra Panel ({panels.length})
          </h2>
          <p className="text-muted-foreground underline-offset-4 decoration-primary/30">
            Xem lại kết quả tự động tách và điều chỉnh nếu cần.
          </p>
        </div>
        <div className="flex gap-4">
          <Button 
            variant="outline" 
            onClick={prevStep} 
            className="rounded-2xl border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20 px-6 h-12 transition-all duration-300 font-bold tracking-wide active:scale-95"
          >
            <ChevronLeft className="w-4 h-4 mr-2" /> Quay lại
          </Button>
          <Button 
            onClick={nextStep} 
            className="relative group overflow-hidden rounded-2xl bg-primary px-8 h-12 transition-all duration-300 shadow-[0_0_20px_rgba(var(--color-primary),0.3)] hover:shadow-[0_0_30px_rgba(var(--color-primary),0.5)] active:scale-95"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-shimmer" />
            <span className="relative flex items-center font-black text-white uppercase tracking-tighter">
              Tiếp tục <ChevronRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </span>
          </Button>
        </div>
      </div>

      {/* Toolbar for Bulk Actions */}
      {panels.length > 0 && (
        <div className="flex items-center justify-between p-4 glass rounded-2xl border-white/5 bg-white/5">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer" onClick={toggleSelectAll}>
              <Checkbox
                checked={selectedIds.size === panels.length && panels.length > 0}
                className="border-white/20 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
              />
              <span className="text-sm font-medium">Chọn tất cả</span>
            </div>
            {selectedIds.size > 0 && (
              <div className="h-4 w-px bg-white/10 mx-2" />
            )}
            {selectedIds.size > 0 && (
              <Button
                variant="destructive"
                size="sm"
                onClick={deleteSelected}
                className="rounded-lg h-9 px-4 animate-in slide-in-from-left-2 duration-300"
              >
                <Trash2 className="w-4 h-4 mr-2" /> Xóa các mục đã chọn ({selectedIds.size})
              </Button>
            )}
          </div>
          <div className="text-xs text-muted-foreground font-medium uppercase tracking-widest px-4">
            {selectedIds.size} / {panels.length} selected
          </div>
        </div>
      )}

      {/* Grid Content */}
      <ScrollArea className="h-[calc(100vh-340px)] rounded-3xl border border-white/5 bg-white/5 p-6 glass">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
          {panels.length === 0 ? (
            <div className="col-span-full h-64 flex flex-col items-center justify-center text-muted-foreground">
              <LayoutGrid className="w-12 h-12 mb-4 opacity-20" />
              <p>Không có panel nào được tìm thấy.</p>
              <Button variant="link" onClick={() => setCurrentStep('upload')}>Quay lại bước tải lên</Button>
            </div>
          ) : (
            panels.map((panel, i) => (
              <Card
                key={panel.id}
                onClick={() => openPanelDetail(i)}
                className={`group overflow-hidden border-white/5 bg-white/5 hover:border-primary/50 hover:bg-white/10 transition-all duration-300 relative rounded-2xl cursor-pointer ${selectedIds.has(panel.id) ? 'ring-2 ring-primary ring-offset-4 ring-offset-background' : ''}`}
              >
                {/* Always Visible Controls */}
                <div className="absolute top-2 right-2 flex gap-2 z-20">
                  <div
                    onClick={(e) => toggleSelect(e, panel.id)}
                    className="p-1.5 bg-black/60 backdrop-blur-md rounded-lg border border-white/10 hover:bg-primary/20 transition-colors"
                  >
                    <Checkbox
                      checked={selectedIds.has(panel.id)}
                      className="border-white/40 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                    />
                  </div>
                  <button
                    onClick={(e) => removePanel(e, panel.id)}
                    className="p-1.5 bg-destructive/80 text-white rounded-lg hover:bg-destructive transition-colors shadow-lg"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="absolute bottom-2 left-2 bg-black/60 backdrop-blur-md px-2 py-1 rounded-md text-[10px] font-bold text-white z-10">
                  #{i + 1}
                </div>

                <CardContent className="p-2 h-48 overflow-hidden relative bg-black/40">
                  <img
                    src={panel.thumbnail}
                    alt={`Panel ${i + 1}`}
                    className="w-full h-full object-contain transition-transform duration-500 group-hover:scale-105"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                  <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    <Maximize2 className="w-6 h-6 text-white/50" />
                  </div>
                </CardContent>
              </Card>
            ))
          )}

          <button
            onClick={() => setCurrentStep('upload')}
            className="h-48 border-2 border-dashed border-white/5 rounded-2xl flex flex-col items-center justify-center hover:border-primary/30 hover:bg-white/5 transition-all group"
          >
            <Plus className="w-8 h-8 text-muted-foreground group-hover:text-primary transition-colors" />
            <span className="text-xs text-muted-foreground mt-2 font-medium">Thêm thủ công</span>
          </button>
        </div>
      </ScrollArea>

      {/* Lightbox Dialog */}
      <Dialog open={selectedIdx !== null} onOpenChange={(open) => !open && closeLightbox()}>
        <DialogContent
          showCloseButton={false}
          className="w-[50vw] max-w-[50vw] sm:max-w-[50vw] h-[70vh] max-h-[70vh] p-0 border-white/5 bg-black/95 backdrop-blur-2xl group/modal z-[100] rounded-[40px] shadow-2xl overflow-hidden flex flex-col items-center justify-center border"
        >
          <DialogHeader className="sr-only">
            <DialogTitle>Xem chi tiết Panel</DialogTitle>
            <DialogDescription>Cố định 70% ngang và dọc màn hình</DialogDescription>
          </DialogHeader>

          <div className="absolute top-6 right-6 z-[110] flex items-center gap-4">
            {isSavingCrop && (
              <div className="flex items-center gap-2 px-4 py-2 bg-primary/20 backdrop-blur-md rounded-full border border-primary/20 animate-in fade-in zoom-in-95">
                <Loader2 className="w-4 h-4 text-primary animate-spin" />
                <span className="text-[10px] font-bold text-primary uppercase tracking-widest">Đang tự động lưu...</span>
              </div>
            )}
            <Button variant="ghost" size="icon" onClick={() => setSelectedIdx(null)} className="rounded-full h-10 w-10 bg-black/60 hover:bg-black/90 text-white shadow-2xl backdrop-blur-xl border border-white/10">
              <X className="w-5 h-5" />
            </Button>
          </div>

          <div className="relative w-full h-full flex flex-col items-center justify-center p-6 overflow-hidden">
            {/* Navigation Arrows */}
            {selectedIdx !== null && selectedIdx > 0 && (
              <button
                onClick={(e) => { e.stopPropagation(); goToPrev(); }}
                className="absolute left-6 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-black/60 hover:bg-black/90 border border-white/20 text-white transition-all z-[120] backdrop-blur-md shadow-2xl"
              >
                <ChevronLeft className="w-6 h-6" />
              </button>
            )}

            {selectedIdx !== null && selectedIdx < panels.length - 1 && (
              <button
                onClick={(e) => { e.stopPropagation(); goToNext(); }}
                className="absolute right-6 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-black/60 hover:bg-black/90 border border-white/20 text-white transition-all z-[120] backdrop-blur-md shadow-2xl"
              >
                <ChevronRight className="w-6 h-6" />
              </button>
            )}

            {/* Main Image / Crop Grid */}
            {selectedIdx !== null && (
              <div className="w-full h-full flex flex-col items-center justify-center animate-in zoom-in-95 duration-300">
                {isEditingCrop && selectedIdx !== null && panels[selectedIdx].originalImageRef ? (
                  <div className="w-full h-full flex items-center justify-center overflow-hidden">
                    <ReactCrop
                      key={selectedIdx} // Force reset grid state when switching panels
                      crop={crop}
                      onChange={(c) => setCrop(c)}
                      onComplete={(c) => saveEditedCrop(c)}
                      className="max-w-full max-h-full"
                    >
                      <img
                        ref={(el) => {
                          imgRef.current = el;
                        }}
                        src={panels[selectedIdx].originalImageRef}
                        onLoad={onImageLoad}
                        style={{ maxHeight: 'calc(70vh - 120px)', maxWidth: '100%', objectFit: 'contain', display: 'block' }}
                        alt="Original Webtoon Page"
                      />
                    </ReactCrop>
                  </div>
                ) : (
                  <div className="w-full h-full flex items-center justify-center py-4">
                    <img
                      src={panels[selectedIdx].base64}
                      alt={`Panel ${selectedIdx + 1}`}
                      className="max-w-full max-h-[85vh] object-contain rounded-md shadow-[0_0_100px_rgba(0,0,0,0.9)] animate-in fade-in duration-500"
                    />
                  </div>
                )}

                <div className="mt-4 mb-2 px-4 py-1.5 bg-black/60 backdrop-blur-xl rounded-full text-white text-[10px] font-bold border border-white/20 shadow-2xl shrink-0 uppercase tracking-widest">
                  {selectedIdx + 1} / {panels.length} | Thả chuột để tự động lưu
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
