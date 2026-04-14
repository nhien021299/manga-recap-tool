import { useRecapStore } from "@/store/useRecapStore";
import { Button } from "@/components/ui/button";
import {
  ChevronRight,
  ChevronLeft,
  Trash2,
  Plus,
  Download,
  GripHorizontal,
  Loader2,
  Maximize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  LocateFixed,
} from "lucide-react";
import { useState, useRef, useEffect, useCallback, useLayoutEffect, useMemo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { cropSceneFromStrip, generateThumbnail, blobToBase64 } from "@/lib/utils/imageUtils";
import type { Scene, Panel } from "@/types";

type TransformMode =
  | "move"
  | "top"
  | "bottom"
  | "left"
  | "right"
  | "top-left"
  | "top-right"
  | "bottom-left"
  | "bottom-right";

type SceneRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

interface SceneOverlayProps {
  scene: Scene;
  scaleFactor: number;
  onTransformPreview: (id: string, mode: TransformMode, deltaX: number, deltaY: number) => void;
  onTransformCommit: (id: string) => void;
  onTransformCancel: (id: string) => void;
  onSelectScene: (id: string) => void;
  removeScene: (id: string) => void;
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const getSceneToneClass = (scene: Scene): string => {
  const confidence = scene.confidence ?? 0.5;
  if (confidence < 0.45) return "border-red-400/90 bg-red-400/12";
  if (confidence < 0.7) return "border-amber-300/90 bg-amber-300/10";
  return "border-cyan-400/90 bg-cyan-400/10";
};

const normalizeScene = (scene: Scene, stripWidth: number): Scene => {
  const x = clamp(scene.x ?? 0, 0, Math.max(0, stripWidth - 1));
  const width = clamp(scene.width ?? stripWidth, 1, Math.max(1, stripWidth - x));
  return { ...scene, x, width };
};

const sceneToRect = (scene: Scene): SceneRect => ({
  x: scene.x ?? 0,
  y: scene.y,
  width: scene.width ?? 1,
  height: scene.height,
});

const applyTransform = (
  rect: SceneRect,
  mode: TransformMode,
  deltaX: number,
  deltaY: number,
  stripWidth: number,
  totalVirtualHeight: number,
  minSceneWidth: number,
  minSceneHeight: number
): SceneRect => {
  let left = rect.x;
  let top = rect.y;
  let right = rect.x + rect.width;
  let bottom = rect.y + rect.height;

  if (mode === "move") {
    left = clamp(left + deltaX, 0, stripWidth - rect.width);
    right = left + rect.width;
    top = clamp(top + deltaY, 0, totalVirtualHeight - rect.height);
    bottom = top + rect.height;
  } else {
    const affectsTop = mode === "top" || mode === "top-left" || mode === "top-right";
    const affectsBottom = mode === "bottom" || mode === "bottom-left" || mode === "bottom-right";
    const affectsLeft = mode === "left" || mode === "top-left" || mode === "bottom-left";
    const affectsRight = mode === "right" || mode === "top-right" || mode === "bottom-right";

    if (affectsTop) {
      top = clamp(top + deltaY, 0, bottom - minSceneHeight);
    }
    if (affectsBottom) {
      bottom = clamp(bottom + deltaY, top + minSceneHeight, totalVirtualHeight);
    }
    if (affectsLeft) {
      left = clamp(left + deltaX, 0, right - minSceneWidth);
    }
    if (affectsRight) {
      right = clamp(right + deltaX, left + minSceneWidth, stripWidth);
    }
  }

  return {
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
  };
};

const SceneOverlay = ({
  scene,
  scaleFactor,
  onTransformPreview,
  onTransformCommit,
  onTransformCancel,
  onSelectScene,
  removeScene,
}: SceneOverlayProps) => {
  const [dragMode, setDragMode] = useState<TransformMode | null>(null);
  const pointerHostRef = useRef<HTMLDivElement>(null);
  const activePointerIdRef = useRef<number | null>(null);
  const lastPoint = useRef({ x: 0, y: 0 });

  const sceneX = scene.x ?? 0;
  const sceneWidth = scene.width ?? 1;
  const scaledX = sceneX * scaleFactor;
  const scaledY = scene.y * scaleFactor;
  const scaledW = sceneWidth * scaleFactor;
  const scaledH = scene.height * scaleFactor;

  const beginDrag = (e: React.PointerEvent, mode: TransformMode) => {
    setDragMode(mode);
    onSelectScene(scene.id);
    lastPoint.current = { x: e.clientX, y: e.clientY };
    activePointerIdRef.current = e.pointerId;
    pointerHostRef.current?.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragMode || activePointerIdRef.current !== e.pointerId) return;
    const deltaX = (e.clientX - lastPoint.current.x) / scaleFactor;
    const deltaY = (e.clientY - lastPoint.current.y) / scaleFactor;
    onTransformPreview(scene.id, dragMode, deltaX, deltaY);
    lastPoint.current = { x: e.clientX, y: e.clientY };
  };

  const endDrag = (e: React.PointerEvent, cancel: boolean) => {
    if (activePointerIdRef.current !== e.pointerId) return;
    pointerHostRef.current?.releasePointerCapture(e.pointerId);
    activePointerIdRef.current = null;
    setDragMode(null);
    if (cancel) {
      onTransformCancel(scene.id);
      return;
    }
    onTransformCommit(scene.id);
  };

  const Handle = ({
    mode,
    className,
    title,
  }: {
    mode: TransformMode;
    className: string;
    title: string;
  }) => (
    <div
      className={className}
      onPointerDown={(e) => {
        e.stopPropagation();
        beginDrag(e, mode);
      }}
      title={title}
    />
  );

  return (
    <div
      ref={pointerHostRef}
      className={`absolute border-2 rounded-none group overflow-hidden pointer-events-auto transition-shadow ${getSceneToneClass(scene)} ${dragMode ? "shadow-2xl z-50 ring-2 ring-cyan-500/60" : "shadow-md z-10"} cursor-move`}
      style={{
        left: `${scaledX}px`,
        top: `${scaledY}px`,
        width: `${scaledW}px`,
        height: `${scaledH}px`,
        touchAction: "none",
      }}
      onPointerDown={(e) => beginDrag(e, "move")}
      onPointerMove={onPointerMove}
      onPointerUp={(e) => endDrag(e, false)}
      onPointerCancel={(e) => endDrag(e, true)}
    >
      <Handle mode="top" title="Resize top" className="absolute -top-px left-2 right-2 h-[2px] cursor-ns-resize bg-white/90" />
      <Handle mode="bottom" title="Resize bottom" className="absolute -bottom-px left-2 right-2 h-[2px] cursor-ns-resize bg-white/90" />
      <Handle mode="left" title="Resize left" className="absolute -left-px top-2 bottom-2 w-[2px] cursor-ew-resize bg-white/90" />
      <Handle mode="right" title="Resize right" className="absolute -right-px top-2 bottom-2 w-[2px] cursor-ew-resize bg-white/90" />
      <Handle mode="top-left" title="Resize top-left" className="absolute -top-[3px] -left-[3px] h-[8px] w-[8px] cursor-nwse-resize border border-white bg-cyan-300" />
      <Handle mode="top-right" title="Resize top-right" className="absolute -top-[3px] -right-[3px] h-[8px] w-[8px] cursor-nesw-resize border border-white bg-cyan-300" />
      <Handle mode="bottom-left" title="Resize bottom-left" className="absolute -bottom-[3px] -left-[3px] h-[8px] w-[8px] cursor-nesw-resize border border-white bg-cyan-300" />
      <Handle mode="bottom-right" title="Resize bottom-right" className="absolute -bottom-[3px] -right-[3px] h-[8px] w-[8px] cursor-nwse-resize border border-white bg-cyan-300" />

      <div className="absolute top-1 left-1/2 -translate-x-1/2 p-1 bg-black/70 border border-white/30 opacity-85 pointer-events-none">
        <GripHorizontal className="w-4 h-4 text-white" />
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
  const {
    virtualStrip,
    totalVirtualHeight,
    stripWidth,
    scenes,
    setScenes,
    removeScene,
    setPanels,
    setCurrentStep,
    aspectRatio,
  } = useRecapStore();

  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [isSavingExport, setIsSavingExport] = useState(false);
  const [preparedPanels, setPreparedPanels] = useState<Panel[] | null>(null);
  const [preparedPanelsKey, setPreparedPanelsKey] = useState<string | null>(null);
  const [activeSceneId, setActiveSceneId] = useState<string | null>(null);
  const [dragPreviewById, setDragPreviewById] = useState<Record<string, SceneRect>>({});
  const parentRef = useRef<HTMLDivElement>(null);
  const sceneItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const dragPreviewRef = useRef<Record<string, SceneRect>>({});

  const MIN_ZOOM = 0.2;
  const MAX_ZOOM = 2.5;
  const DEFAULT_ZOOM = 0.6;
  const minSceneWidth = Math.max(80, Math.round(stripWidth * 0.08));
  const minSceneHeight = Math.max(80, Math.round(stripWidth * 0.08));

  useEffect(() => {
    dragPreviewRef.current = dragPreviewById;
  }, [dragPreviewById]);

  const getFitScaleFactor = useCallback(() => {
    const container = parentRef.current;
    if (!container) return 1;
    const padding = window.innerWidth >= 1024 ? 128 : 64;
    const availableWidth = container.clientWidth - padding;
    const actualWidth = Math.min(availableWidth, 800);
    return actualWidth / Math.max(stripWidth, 1);
  }, [stripWidth]);

  const [fitScale, setFitScale] = useState(1);
  const [zoomLevel, setZoomLevel] = useState(DEFAULT_ZOOM);
  const previewScale = fitScale * zoomLevel;

  useEffect(() => {
    const updateScale = () => setFitScale(getFitScaleFactor());
    updateScale();
    window.addEventListener("resize", updateScale);
    return () => window.removeEventListener("resize", updateScale);
  }, [getFitScaleFactor]);

  const updateZoom = useCallback((nextZoom: number) => {
    setZoomLevel(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom)));
  }, []);

  const normalizedScenes = scenes.map((scene) => normalizeScene(scene, stripWidth));
  const sortedSceneIds = [...normalizedScenes]
    .sort((a, b) => a.y - b.y)
    .map((scene) => scene.id);
  const sceneById = normalizedScenes.reduce<Record<string, Scene>>((acc, scene) => {
    acc[scene.id] = scene;
    return acc;
  }, {});

  const displayScenes = sortedSceneIds.map((id) => {
    const base = sceneById[id];
    const preview = dragPreviewById[id];
    if (!base) return null;
    if (!preview) return base;
    return { ...base, ...preview, isAuto: false };
  }).filter(Boolean) as Scene[];
  const activeScene = activeSceneId
    ? displayScenes.find((scene) => scene.id === activeSceneId) ?? null
    : null;
  const extractionKey = useMemo(
    () =>
      JSON.stringify({
        stripWidth,
        scenes: [...displayScenes]
          .sort((a, b) => a.y - b.y)
          .map((scene) => ({
            id: scene.id,
            x: Math.round(scene.x ?? 0),
            y: Math.round(scene.y),
            width: Math.round(scene.width ?? stripWidth),
            height: Math.round(scene.height),
          })),
      }),
    [displayScenes, stripWidth]
  );

  const rowVirtualizer = useVirtualizer({
    count: virtualStrip.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => virtualStrip[index].scaledHeight * previewScale,
    overscan: 2,
  });
  const previousScaleRef = useRef(previewScale);

  useLayoutEffect(() => {
    const container = parentRef.current;
    if (!container) return;
    const previousScale = Math.max(previousScaleRef.current, 0.0001);
    const canonicalY = container.scrollTop / previousScale;
    rowVirtualizer.measure();
    container.scrollTop = canonicalY * previewScale;
    previousScaleRef.current = previewScale;
  }, [previewScale, rowVirtualizer]);

  const onTransformPreview = useCallback((id: string, mode: TransformMode, deltaX: number, deltaY: number) => {
    setDragPreviewById((prev) => {
      const source = prev[id] ?? sceneToRect(sceneById[id] ?? { id, x: 0, y: 0, width: stripWidth, height: minSceneHeight, isAuto: false });
      const next = applyTransform(
        source,
        mode,
        deltaX,
        deltaY,
        stripWidth,
        totalVirtualHeight,
        minSceneWidth,
        minSceneHeight
      );
      return { ...prev, [id]: next };
    });
    setActiveSceneId(id);
  }, [minSceneHeight, minSceneWidth, sceneById, stripWidth, totalVirtualHeight]);

  const onTransformCommit = useCallback((id: string) => {
    const draft = dragPreviewRef.current[id];
    if (!draft) return;
    setScenes(useRecapStore.getState().scenes.map((scene) => {
      if (scene.id !== id) return scene;
      return { ...scene, ...draft, isAuto: false };
    }));
    setDragPreviewById((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, [setScenes]);

  const onTransformCancel = useCallback((id: string) => {
    setDragPreviewById((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  const scrollSceneInList = useCallback((id: string) => {
    sceneItemRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const locateCurrentScene = useCallback(() => {
    const container = parentRef.current;
    if (!container || displayScenes.length === 0) return;

    const canonicalCenterY = (container.scrollTop + container.clientHeight / 2) / previewScale;
    let found = displayScenes.find((scene) => (
      canonicalCenterY >= scene.y && canonicalCenterY <= scene.y + scene.height
    ));

    if (!found) {
      let bestDistance = Number.POSITIVE_INFINITY;
      for (const scene of displayScenes) {
        const center = scene.y + scene.height / 2;
        const distance = Math.abs(center - canonicalCenterY);
        if (distance < bestDistance) {
          bestDistance = distance;
          found = scene;
        }
      }
    }

    if (!found) return;
    setActiveSceneId(found.id);
    scrollSceneInList(found.id);
  }, [displayScenes, previewScale, scrollSceneInList]);

  const addManualScene = useCallback(() => {
    const currentScroll = parentRef.current?.scrollTop || 0;
    const newY = currentScroll / previewScale;
    useRecapStore.getState().addScene({
      id: `scene-manual-${Date.now()}`,
      x: 0,
      y: newY,
      width: stripWidth,
      height: Math.round(stripWidth / aspectRatio),
      isAuto: false,
    });
  }, [aspectRatio, previewScale, stripWidth]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTypingTarget = !!target && (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      );

      if (isTypingTarget || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }

      const key = event.key.toLowerCase();

      if (key === "a") {
        event.preventDefault();
        addManualScene();
        return;
      }

      if (key === "s") {
        event.preventDefault();
        locateCurrentScene();
        return;
      }

      if (key === "d" && activeSceneId) {
        event.preventDefault();
        removeScene(activeSceneId);
        setActiveSceneId(null);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeSceneId, addManualScene, locateCurrentScene, removeScene]);

  const preparePanels = useCallback(async (progressScale = 100): Promise<Panel[]> => {
    const canReusePrepared = preparedPanelsKey === extractionKey && preparedPanels && preparedPanels.length > 0;
    if (canReusePrepared) return preparedPanels;

    const scenesToExport = [...displayScenes].sort((a, b) => a.y - b.y);
    const allProcessedPanels: Panel[] = [];

    for (let i = 0; i < scenesToExport.length; i++) {
      const scene = scenesToExport[i];
      const sceneBlob = await cropSceneFromStrip(virtualStrip, scene, stripWidth);
      const thumbnail = await generateThumbnail(sceneBlob);
      const base64 = await blobToBase64(sceneBlob);

      allProcessedPanels.push({
        id: scene.id,
        blob: sceneBlob,
        base64,
        thumbnail,
        width: scene.width ?? stripWidth,
        height: scene.height,
        order: i,
      });

      setExportProgress(Math.round(((i + 1) / scenesToExport.length) * progressScale));
    }

    setPreparedPanels(allProcessedPanels);
    setPreparedPanelsKey(extractionKey);
    return allProcessedPanels;
  }, [displayScenes, extractionKey, preparedPanels, preparedPanelsKey, stripWidth, virtualStrip]);

  const exportScenes = async () => {
    if (displayScenes.length === 0) return;

    const canReusePrepared = preparedPanelsKey === extractionKey && preparedPanels && preparedPanels.length > 0;
    if (canReusePrepared) {
      setPanels(preparedPanels);
      setCurrentStep("script");
      return;
    }

    setIsExporting(true);
    setExportProgress(0);
    try {
      const allProcessedPanels = await preparePanels(100);
      setPanels(allProcessedPanels);
      setCurrentStep("script");
    } catch (error) {
      console.error(error);
    } finally {
      setIsExporting(false);
    }
  };

  const savePanelsToFolder = async () => {
    if (displayScenes.length === 0) return;

    const picker = (window as Window & {
      showDirectoryPicker?: () => Promise<{
        getFileHandle: (name: string, options: { create: boolean }) => Promise<{
          createWritable: () => Promise<{ write: (data: Blob) => Promise<void>; close: () => Promise<void> }>;
        }>;
      }>;
    }).showDirectoryPicker;

    if (!picker) {
      window.alert("Trình duyệt hiện tại chưa hỗ trợ chọn thư mục để export.");
      return;
    }

    try {
      const dirHandle = await picker();
      setIsSavingExport(true);
      setExportProgress(0);

      const canReusePrepared = preparedPanelsKey === extractionKey && preparedPanels && preparedPanels.length > 0;
      const panelsToSave = canReusePrepared ? preparedPanels : await preparePanels(50);
      const startProgress = canReusePrepared ? 0 : 50;
      const progressRange = canReusePrepared ? 100 : 50;

      for (let i = 0; i < panelsToSave.length; i++) {
        const panel = panelsToSave[i];
        const fileName = `scene-${String(i + 1).padStart(3, "0")}.png`;
        const fileHandle = await dirHandle.getFileHandle(fileName, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(panel.blob);
        await writable.close();
        setExportProgress(startProgress + Math.round(((i + 1) / panelsToSave.length) * progressRange));
      }

      setPanels(panelsToSave);
    } catch (error) {
      console.error(error);
    } finally {
      setIsSavingExport(false);
    }
  };

  const prevStep = () => setCurrentStep("upload");
  const onSceneListWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.scrollTop += e.deltaY;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] animate-in fade-in duration-500 gap-4">
      <div className="flex items-center justify-between bg-white/5 p-4 rounded-3xl border border-white/5 glass shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
            Tách Panel
          </h2>
          <span className="px-3 py-1 rounded-full bg-primary/20 text-primary text-[10px] font-bold border border-primary/20 uppercase tracking-wider">
            {displayScenes.length} scenes
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={prevStep} disabled={isExporting || isSavingExport} className="rounded-xl border-white/10 px-4 h-10 font-bold active:scale-95">
            <ChevronLeft className="w-4 h-4 mr-1" /> Quay lại
          </Button>
          <Button onClick={exportScenes} disabled={isExporting || isSavingExport} size="sm" className="rounded-xl bg-primary text-primary-foreground px-6 h-10 shadow-glow font-black border-none relative overflow-hidden group">
            {isExporting ? (
              <span className="flex items-center"><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Xuat ({exportProgress}%)</span>
            ) : (
              <span className="flex items-center">Tiếp tục<ChevronRight className="w-5 h-5 ml-1 group-hover:translate-x-1 transition-transform" /></span>
            )}
          </Button>
        </div>
      </div>

      <div className="flex flex-col md:flex-row gap-6 flex-1 min-h-0 overflow-hidden">
        <div className="w-full md:w-[74%] lg:w-[76%] glass border border-white/5 rounded-3xl overflow-hidden relative flex flex-col bg-black/40 h-full">
          {activeScene && (
            <div className="absolute top-14 left-4 z-10 flex items-center gap-2 bg-black/70 border border-cyan-400/40 px-2.5 py-1.5 text-[10px] font-mono text-cyan-100">
              <span className="uppercase tracking-widest text-cyan-300/90">Scene</span>
              <span>#{displayScenes.findIndex((s) => s.id === activeScene.id) + 1}</span>
              <span className="text-white/60">|</span>
              <span>X:{Math.round(activeScene.x ?? 0)}</span>
              <span>Y:{Math.round(activeScene.y)}</span>
              <span>W:{Math.round(activeScene.width ?? stripWidth)}</span>
              <span>H:{Math.round(activeScene.height)}</span>
            </div>
          )}
          <div className="absolute top-4 right-4 z-10 flex items-center gap-1.5 rounded-xl border border-white/15 bg-black/60 p-2 backdrop-blur-md">
            <Button size="icon-sm" variant="ghost" className="h-9 w-9 rounded-lg text-white/70 hover:text-white" onClick={() => updateZoom(zoomLevel - 0.1)} title="Zoom out">
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="min-w-14 text-center text-xs font-mono text-white/75">{Math.round(zoomLevel * 100)}%</span>
            <Button size="icon-sm" variant="ghost" className="h-9 w-9 rounded-lg text-white/70 hover:text-white" onClick={() => updateZoom(zoomLevel + 0.1)} title="Zoom in">
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button size="icon-sm" variant="ghost" className="h-9 w-9 rounded-lg text-white/70 hover:text-white" onClick={() => updateZoom(DEFAULT_ZOOM)} title="Reset zoom">
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
          <div className="absolute top-[5.25rem] right-4 z-10 flex items-center gap-1.5">
            <Button
              size="sm"
              variant="outline"
              className="h-9 text-xs border-white/20 text-white/80 hover:bg-white/10 rounded-lg shrink-0 px-3"
              onClick={locateCurrentScene}
              title="Locate current scene in list (S)"
            >
              <LocateFixed className="w-4 h-4 mr-1.5" /> Locate (S)
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-9 text-xs border-primary/30 text-primary hover:bg-primary/10 rounded-lg shrink-0 px-3"
              onClick={addManualScene}
              title="Add manual scene (A)"
            >
              <Plus className="w-4 h-4 mr-1.5" /> Add (A)
            </Button>
          </div>

          <div ref={parentRef} className="flex-1 overflow-y-auto w-full custom-scrollbar relative mx-auto bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.04),transparent_30%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_16%)] px-8 lg:px-16">
            <div
              style={{
                height: `${rowVirtualizer.getTotalSize()}px`,
                width: "100%",
                position: "relative",
                maxWidth: "800px",
                margin: "0 auto",
              }}
            >
              <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}>
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const imgMeta = virtualStrip[virtualRow.index];
                  return (
                    <div
                      key={virtualRow.key}
                      style={{
                        position: "absolute",
                        top: 0,
                        left: "50%",
                        width: `${stripWidth * previewScale}px`,
                        height: `${virtualRow.size}px`,
                        transform: `translate(-50%, ${virtualRow.start}px)`,
                      }}
                    >
                      <img src={imgMeta.objectUrl} alt="Strip Segment" className="w-full h-full object-cover pointer-events-none opacity-80" />
                    </div>
                  );
                })}
              </div>

              <div style={{ position: "absolute", top: 0, left: "50%", width: `${stripWidth * previewScale}px`, height: "100%", pointerEvents: "none", transform: "translateX(-50%)" }}>
                {displayScenes.map((scene) => (
                  <SceneOverlay
                    key={scene.id}
                    scene={scene}
                    scaleFactor={previewScale}
                    onTransformPreview={onTransformPreview}
                    onTransformCommit={onTransformCommit}
                    onTransformCancel={onTransformCancel}
                    onSelectScene={(id) => setActiveSceneId(id)}
                    removeScene={removeScene}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="w-full md:w-[26%] lg:w-[24%] flex flex-col min-h-0 glass border border-white/5 rounded-3xl overflow-hidden bg-black/20 p-4 gap-4 h-full">
          <div className="flex justify-between items-center px-2 shrink-0 gap-2">
            <h3 className="font-bold text-white/80 tracking-wider text-xs">Danh sách scene ({displayScenes.length})</h3>
            <Button
              size="sm"
              variant="outline"
              className="h-10 text-sm border-primary/20 text-primary hover:bg-primary/10 rounded-lg shrink-0 px-3"
              onClick={savePanelsToFolder}
              disabled={isExporting || isSavingExport || displayScenes.length === 0}
            >
              {isSavingExport ? (
                <span className="flex items-center"><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Export to ({exportProgress}%)</span>
              ) : (
                <span className="flex items-center"><Download className="w-4 h-4 mr-2" /> Export to</span>
              )}
            </Button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-1" onWheel={onSceneListWheel}>
            <div className="space-y-3 pb-8">
              {displayScenes.map((scene, index) => (
                <div
                  key={scene.id}
                  ref={(node) => {
                    sceneItemRefs.current[scene.id] = node;
                  }}
                  className={`p-3 bg-white/5 border rounded-none cursor-pointer group transition-all duration-150 relative ${activeSceneId === scene.id
                    ? "border-cyan-400/80 ring-1 ring-cyan-400/45 bg-cyan-500/10"
                    : "border-white/5 hover:border-cyan-500/35"
                    }`}
                  onClick={() => {
                    setActiveSceneId(scene.id);
                    parentRef.current?.scrollTo({ top: scene.y * previewScale, behavior: "smooth" });
                  }}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-16 bg-black flex items-center justify-center rounded-lg border border-white/10 shrink-0 text-white/20 relative overflow-hidden group-hover:border-cyan-500/50">
                      <Maximize2 className="w-5 h-5 group-hover:text-cyan-500 transition-colors" />
                      {scene.isAuto && <span className="absolute top-0 right-0 bg-primary/20 text-primary text-[8px] font-bold px-1 rounded-bl">A</span>}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-white/80 font-bold text-xs">Scene {index + 1}</h4>
                      <p className="text-[10px] text-white/40 font-mono mt-1">X: {Math.round(scene.x ?? 0)}px</p>
                      <p className="text-[10px] text-white/40 font-mono">Y: {Math.round(scene.y)}px</p>
                      <p className="text-[10px] text-white/40 font-mono">W: {Math.round(scene.width ?? stripWidth)}px</p>
                      <p className="text-[10px] text-white/40 font-mono">H: {Math.round(scene.height)}px</p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeScene(scene.id);
                        if (activeSceneId === scene.id) {
                          setActiveSceneId(null);
                        }
                      }}
                      title="Delete scene (D)"
                      className="p-2 rounded hover:bg-destructive/10 text-white/30 hover:text-destructive transition-colors shrink-0"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


