import { useRecapStore } from "@/store/useRecapStore";
import { Button } from "@/components/ui/button";
import { ChevronRight, ChevronLeft, Trash2, Plus, GripHorizontal, Loader2, Maximize2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useState, useRef, useEffect, useCallback } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { cropSceneFromStrip, generateThumbnail, blobToBase64 } from "@/lib/utils/imageUtils";
import { STRIP_WIDTH } from "@/types";
import type { Scene } from "@/types";

interface SceneOverlayProps {
  scene: Scene;
  scaleFactor: number;
  handleDragScene: (id: string, deltaY: number) => void;
  removeScene: (id: string) => void;
}

const SceneOverlay = ({ scene, scaleFactor, handleDragScene, removeScene }: SceneOverlayProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const lastY = useRef(0);

  const onPointerDown = (e: React.PointerEvent) => {
    setIsDragging(true);
    lastY.current = e.clientY;
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!isDragging) return;
    const delta = e.clientY - lastY.current;
    
    // Convert DOM delta viewport pixels to virtual scale delta
    const virtualDelta = delta / scaleFactor;
    handleDragScene(scene.id, virtualDelta);
    
    lastY.current = e.clientY;
  };

  const onPointerUp = (e: React.PointerEvent) => {
    setIsDragging(false);
    e.currentTarget.releasePointerCapture(e.pointerId);
  };

  const scaledY = scene.y * scaleFactor;
  const scaledH = scene.height * scaleFactor;

  return (
    <div 
      className={`absolute left-0 right-0 border-2 rounded-xl border-cyan-400 group overflow-hidden pointer-events-auto cursor-ns-resize transition-shadow ${isDragging ? 'shadow-2xl z-50 ring-2 ring-cyan-500/50 bg-cyan-400/20' : 'shadow-md z-10 hover:bg-cyan-400/10'}`}
      style={{ top: `${scaledY}px`, height: `${scaledH}px`, touchAction: 'none' }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div className="absolute top-2 left-1/2 -translate-x-1/2 p-2 bg-black/60 backdrop-blur rounded-full opacity-50 group-hover:opacity-100 transition-opacity">
         <GripHorizontal className="w-5 h-5 text-white" />
      </div>
      <div className="absolute top-2 right-2 flex gap-1 z-20">
          <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => removeScene(scene.id)}
          className="p-1.5 bg-destructive text-white rounded hover:bg-red-600 transition-colors shadow"
          >
          <Trash2 className="w-3.5 h-3.5" />
          </button>
      </div>
    </div>
  );
};

export function StepExtract() {
  const { virtualStrip, totalVirtualHeight, scenes, setScenes, removeScene, setPanels, setCurrentStep, aspectRatio } = useRecapStore();
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  
  const parentRef = useRef<HTMLDivElement>(null);

  const getScaleFactor = () => {
    const container = parentRef.current;
    if (!container) return 1;
    // Account for px-8 (64px) or px-16 (128px) padding
    const padding = window.innerWidth >= 1024 ? 128 : 64;
    const availableWidth = container.clientWidth - padding;
    const actualWidth = Math.min(availableWidth, 800); // 800px max-width clamp
    return actualWidth / STRIP_WIDTH;
  };

  const [scale, setScale] = useState(1);

  // Update scale on mount/resize
  useEffect(() => {
    const updateScale = () => setScale(getScaleFactor());
    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, []);

  // Map Virtual Strip to React Virtualizer
  const rowVirtualizer = useVirtualizer({
    count: virtualStrip.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => virtualStrip[index].scaledHeight * scale,
    overscan: 2,
  });

  const handleDragScene = useCallback((id: string, deltaY: number) => {
    setScenes(useRecapStore.getState().scenes.map(s => {
      if (s.id !== id) return s;
      let newY = s.y + deltaY;
      if (newY < 0) newY = 0;
      if (newY + s.height > totalVirtualHeight) newY = totalVirtualHeight - s.height;
      return { ...s, y: newY, isAuto: false };
    }));
  }, [totalVirtualHeight, setScenes]);

  const exportScenes = async () => {
    setIsExporting(true);
    setExportProgress(0);
    try {
      const allProcessedPanels = [];
      const scenesToExport = [...scenes].sort((a, b) => a.y - b.y);

      for (let i = 0; i < scenesToExport.length; i++) {
        const scene = scenesToExport[i];
        
        // 1. Crop Canvas
        const sceneBlob = await cropSceneFromStrip(virtualStrip, scene, STRIP_WIDTH);
        
        // 2. Thumb & Base64 // Using same flow as before to feed into Prompt
        const thumbnail = await generateThumbnail(sceneBlob);
        const base64 = await blobToBase64(sceneBlob);

        allProcessedPanels.push({
          id: scene.id,
          blob: sceneBlob,
          base64: base64,
          thumbnail: thumbnail,
          width: STRIP_WIDTH,
          height: scene.height,
          order: i,
        });

        setExportProgress(Math.round(((i + 1) / scenesToExport.length) * 100));
      }

      setPanels(allProcessedPanels);
      setCurrentStep('script');
    } catch (e) {
      console.error(e);
    } finally {
      setIsExporting(false);
    }
  };

  const prevStep = () => setCurrentStep('upload');

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] animate-in fade-in duration-500 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between bg-white/5 p-4 rounded-3xl border border-white/5 glass shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
            Chọn Khung Hình
          </h2>
          <span className="px-3 py-1 rounded-full bg-primary/20 text-primary text-[10px] font-bold border border-primary/20 uppercase tracking-wider">
            {scenes.length} Scenes
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={prevStep} disabled={isExporting} className="rounded-xl border-white/10 px-4 h-10 font-bold active:scale-95">
            <ChevronLeft className="w-4 h-4 mr-1" /> Quay lại
          </Button>
          <Button onClick={exportScenes} disabled={isExporting} size="sm" className="rounded-xl bg-primary text-primary-foreground px-6 h-10 shadow-glow font-black border-none relative overflow-hidden group">
            {isExporting ? (
              <span className="flex items-center"><Loader2 className="w-4 h-4 mr-2 animate-spin"/> Xuất ({exportProgress}%)</span>
            ) : (
              <span className="flex items-center">Tiếp tục <ChevronRight className="w-5 h-5 ml-1 group-hover:translate-x-1 transition-transform" /></span>
            )}
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-col md:flex-row gap-6 flex-1 min-h-0 overflow-hidden">
        {/* Left: ViewFinder Virtual Strip */}
        <div className="w-full md:w-[60%] lg:w-[65%] glass border border-white/5 rounded-3xl overflow-hidden relative flex flex-col bg-black/40 h-full">
           <div className="absolute top-4 left-4 z-10 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg text-xs font-mono text-white/50 border border-white/10 uppercase tracking-widest pointer-events-none">
              Strip Width: {STRIP_WIDTH}px
           </div>
           
           <div ref={parentRef} className="flex-1 overflow-y-auto w-full custom-scrollbar relative mx-auto bg-black/20 px-8 lg:px-16" style={{ scrollBehavior: 'smooth' }}>
              <div
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  width: '100%',
                  position: 'relative',
                  maxWidth: '800px', // Shrink content
                  margin: '0 auto'
                }}
              >
                {/* 1. Underlying Images */}
                <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}>
                  {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                    const imgMeta = virtualStrip[virtualRow.index];
                    return (
                      <div
                        key={virtualRow.key}
                        style={{
                          position: 'absolute',
                          top: 0,
                          left: '50%',
                          width: `${1080 * scale}px`, // Actual strip width in UI
                          height: `${virtualRow.size}px`,
                          transform: `translate(-50%, ${virtualRow.start}px)`,
                        }}
                      >
                        <img 
                          src={imgMeta.objectUrl} 
                          alt="Strip Segment" 
                          className="w-full h-full object-cover pointer-events-none opacity-80"
                        />
                      </div>
                    )
                  })}
                </div>
                
                {/* 2. Scene Overlays Layer */}
                <div style={{ position: 'absolute', top: 0, left: '50%', width: `${1080 * scale}px`, height: '100%', pointerEvents: 'none', transform: 'translateX(-50%)' }}>
                    {scenes.map(scene => (
                        <SceneOverlay 
                          key={scene.id} 
                          scene={scene} 
                          scaleFactor={scale}
                          handleDragScene={handleDragScene}
                          removeScene={removeScene}
                        />
                    ))}
                </div>
              </div>
           </div>
        </div>

        {/* Right: Scene List */}
        <div className="w-full md:w-[40%] lg:w-[35%] flex flex-col glass border border-white/5 rounded-3xl overflow-hidden bg-black/20 p-4 gap-4 h-full">
           <div className="flex justify-between items-center px-2 shrink-0">
             <h3 className="font-bold text-white/80 uppercase tracking-wider text-xs">Danh sách Scene ({scenes.length})</h3>
             <Button
                size="sm"
                variant="outline"
                className="h-8 text-xs border-primary/20 text-primary hover:bg-primary/10 rounded-lg shrink-0 w-auto pointer-events-auto"
                onClick={() => {
                  const currentScroll = parentRef.current?.scrollTop || 0;
                  const newY = currentScroll / scale;
                  useRecapStore.getState().addScene({
                    id: `scene-manual-${Date.now()}`,
                    y: newY,
                    height: Math.round(STRIP_WIDTH / aspectRatio),
                    isAuto: false
                  });
                }}
             >
                <Plus className="w-3.5 h-3.5 mr-1" /> Thêm tại đây
             </Button>
           </div>
           
           <ScrollArea className="flex-1 -mr-4 pr-4">
              <div className="space-y-3 pb-8">
                {scenes.sort((a,b) => a.y - b.y).map((scene, i) => (
                  <div 
                    key={scene.id} 
                    className="p-3 bg-white/5 border border-white/5 hover:border-cyan-500/30 rounded-2xl cursor-pointer group transition-all duration-300 relative"
                    onClick={() => {
                      parentRef.current?.scrollTo({ top: scene.y * scale, behavior: 'smooth' });
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-16 bg-black flex items-center justify-center rounded-lg border border-white/10 shrink-0 text-white/20 relative overflow-hidden group-hover:border-cyan-500/50">
                        <Maximize2 className="w-5 h-5 group-hover:text-cyan-500 transition-colors" />
                        {scene.isAuto && <span className="absolute top-0 right-0 bg-primary/20 text-primary text-[8px] font-bold px-1 rounded-bl">A</span>}
                      </div>
                      <div className="flex-1">
                        <h4 className="text-white/80 font-bold text-xs">Cảnh #{i + 1}</h4>
                        <p className="text-[10px] text-white/40 font-mono mt-1">Y: {Math.round(scene.y)}px</p>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); removeScene(scene.id); }}
                        className="p-2 rounded hover:bg-destructive/10 text-white/30 hover:text-destructive transition-colors shrink-0"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
           </ScrollArea>
        </div>
      </div>
    </div>
  );
}
