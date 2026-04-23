import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { get, set as idbSet } from "idb-keyval";

import {
  type AudioStatus,
  type BenchmarkRecord,
  type ChapterCharacterState,
  DEFAULT_ASPECT,
  STRIP_WIDTH,
  type AppConfig,
  type GeminiLog,
  type Panel,
  type PanelUnderstanding,
  type PanelUnderstandingMeta,
  type RenderConfig,
  type Scene,
  type CharacterScriptContext,
  type ScriptContext,
  type ScriptMeta,
  type Step,
  type StoryMemory,
  type TimelineItem,
  type VirtualStripImage,
  type VoiceConfig,
  type VoiceGenerationProgress,
} from "@/shared/types";

interface RecapState {
  config: AppConfig;
  setConfig: (config: Partial<AppConfig>) => void;
  voiceConfig: VoiceConfig;
  setVoiceConfig: (config: Partial<VoiceConfig>) => void;

  currentStep: Step;
  setCurrentStep: (step: Step) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  progress: number;
  setProgress: (progress: number) => void;
  currentVoiceGeneration: VoiceGenerationProgress | null;
  setCurrentVoiceGeneration: (progress: VoiceGenerationProgress | null) => void;

  aspectRatio: number;
  setAspectRatio: (ratio: number) => void;
  renderConfig: RenderConfig;
  setRenderConfig: (config: Partial<RenderConfig>) => void;

  logs: GeminiLog[];
  addLog: (log: Omit<GeminiLog, "id" | "timestamp">) => void;
  replaceLogs: (logs: GeminiLog[]) => void;
  clearLogs: () => void;

  virtualStrip: VirtualStripImage[];
  totalVirtualHeight: number;
  stripWidth: number;
  setVirtualStrip: (strip: VirtualStripImage[], totalHeight: number, stripWidth: number) => void;

  scenes: Scene[];
  setScenes: (scenes: Scene[]) => void;
  updateScene: (id: string, updates: Partial<Scene>) => void;
  addScene: (scene: Scene) => void;
  removeScene: (id: string) => void;

  panels: Panel[];
  setPanels: (panels: Panel[]) => void;
  addPanels: (panels: Panel[]) => void;

  scriptContext: ScriptContext;
  setScriptContext: (context: Partial<ScriptContext>) => void;
  characterState: ChapterCharacterState | null;
  setCharacterState: (state: ChapterCharacterState | null) => void;
  clearCharacterState: () => void;
  panelUnderstandings: PanelUnderstanding[];
  setPanelUnderstandings: (items: PanelUnderstanding[]) => void;
  panelUnderstandingMeta: PanelUnderstandingMeta;
  setPanelUnderstandingMeta: (meta: PanelUnderstandingMeta) => void;
  storyMemories: StoryMemory[];
  setStoryMemories: (items: StoryMemory[]) => void;

  timeline: TimelineItem[];
  setTimeline: (timeline: TimelineItem[]) => void;
  updateTimelineItem: (index: number, item: Partial<TimelineItem>) => void;
  moveTimelineItem: (fromIndex: number, toIndex: number) => void;
  removeTimelineItem: (index: number) => void;
  duplicateTimelineItem: (index: number) => void;
  resetTimelineItemToAuto: (index: number) => void;
  scriptMeta: ScriptMeta;
  setScriptMeta: (meta: ScriptMeta) => void;
  markScriptOutdated: (reason: string) => void;
  clearScriptData: () => void;
  benchmarkRecords: BenchmarkRecord[];
  addBenchmarkRecord: (record: BenchmarkRecord) => void;
  removeBenchmarkRecord: (id: string) => void;

  init: () => Promise<void>;
  reset: () => void;
}

type PersistedVirtualStripImage = Omit<VirtualStripImage, "objectUrl">;

interface PersistedVirtualStripState {
  stripWidth: number;
  totalVirtualHeight: number;
  images: PersistedVirtualStripImage[];
}

const normalizeAppConfig = (config?: Partial<AppConfig> | null): AppConfig => ({
  apiBaseUrl: (config?.apiBaseUrl || import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").trim(),
  language: config?.language === "en" ? "en" : "vi",
});

const normalizeNumber = (value: unknown, fallback: number): number => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
};

const clamp = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value));

const DEFAULT_TTS_PROVIDER = "vieneu";
const DEFAULT_TTS_VOICE_KEY = "voice_default";
const DEFAULT_TTS_SPEED = 1.15;
const DEFAULT_HOLD_AFTER_MS = 250;
const MIN_HOLD_AFTER_MS = 0;
const MAX_HOLD_AFTER_MS = 3000;
const DEFAULT_OUTPUT_WIDTH = 1080;

const normalizeVoiceConfig = (config?: Partial<VoiceConfig> | null): VoiceConfig => {
  const provider = (config?.provider || import.meta.env.VITE_TTS_PROVIDER || DEFAULT_TTS_PROVIDER).trim() || DEFAULT_TTS_PROVIDER;
  const requestedVoiceKey = (
    config?.voiceKey ||
    import.meta.env.VITE_TTS_VOICE_KEY ||
    DEFAULT_TTS_VOICE_KEY
  ).trim();
  const voiceKey = requestedVoiceKey === "default" ? DEFAULT_TTS_VOICE_KEY : (requestedVoiceKey || DEFAULT_TTS_VOICE_KEY);

  return {
    provider,
    voiceKey,
    speed: Math.max(0.8, Math.min(1.15, normalizeNumber(config?.speed, DEFAULT_TTS_SPEED))),
  };
};

const normalizeRenderConfig = (
  config?: Partial<RenderConfig> | null,
  fallbackAspectRatio = DEFAULT_ASPECT
): RenderConfig => ({
  captionMode: config?.captionMode === "burned" ? "burned" : "off",
  outputWidth: Math.max(720, Math.round(normalizeNumber(config?.outputWidth, DEFAULT_OUTPUT_WIDTH))),
  aspectRatio: normalizeNumber(config?.aspectRatio, fallbackAspectRatio) || fallbackAspectRatio,
});

const EMPTY_SCRIPT_META: ScriptMeta = {
  status: "idle",
  sourceUnits: [],
  rawOutput: "",
  pipeline: "backend-gemini-unified",
};

const EMPTY_PANEL_UNDERSTANDING_META: PanelUnderstandingMeta = {
  panelSignature: "",
  rawOutput: "",
};

const buildCharacterScriptContext = (state: ChapterCharacterState | null): CharacterScriptContext | null => {
  if (!state) return null;

  const activeClusters = state.clusters.filter((cluster) => cluster.status !== "ignored" && cluster.status !== "merged");
  const characters = activeClusters
    .map((cluster) => ({
      clusterId: cluster.clusterId,
      canonicalName: cluster.canonicalName || "",
      displayLabel: cluster.displayLabel || cluster.canonicalName || "",
      lockName: !!cluster.lockName,
    }))
    .filter((item) => item.displayLabel.trim().length > 0 || item.canonicalName.trim().length > 0);

  const activeClusterIds = new Set(characters.map((character) => character.clusterId));
  const panelCharacterRefs = Object.fromEntries(
    state.panelCharacterRefs
      .map((ref) => [ref.panelId, ref.clusterIds.filter((clusterId) => activeClusterIds.has(clusterId))] as const)
      .filter(([, clusterIds]) => clusterIds.length > 0)
  );
  const unknownPanelIds = state.panelCharacterRefs
    .filter((ref) => ref.clusterIds.filter((clusterId) => activeClusterIds.has(clusterId)).length === 0)
    .map((ref) => ref.panelId);

  return {
    chapterId: state.chapterId,
    characters,
    panelCharacterRefs,
    unknownPanelIds,
  };
};

const normalizeSceneRect = (scene: Scene, stripWidth: number): Scene => {
  const x = Math.min(Math.max(scene.x ?? 0, 0), Math.max(0, stripWidth - 1));
  const width = Math.min(Math.max(scene.width ?? stripWidth, 1), Math.max(1, stripWidth - x));
  return { ...scene, x, width };
};

const buildPanelSignature = (panels: Panel[]): string =>
  JSON.stringify(
    panels.map((panel) => ({
      id: panel.id,
      width: panel.width,
      height: panel.height,
      order: panel.order,
    }))
  );

const normalizePanelUnderstanding = (
  item: PanelUnderstanding,
  panelId: string,
  orderIndex: number
): PanelUnderstanding => ({
  panelId: item.panelId || panelId,
  orderIndex: Number.isFinite(item.orderIndex) ? item.orderIndex : orderIndex,
  summary: item.summary || "",
  action: item.action || "",
  emotion: item.emotion || "",
  dialogue: item.dialogue || "",
  cliffhanger: item.cliffhanger || "",
});

const hasReadyAudioData = (item: Partial<TimelineItem>): boolean =>
  item.audioBlob instanceof Blob &&
  typeof item.audioDuration === "number" &&
  Number.isFinite(item.audioDuration) &&
  item.audioDuration > 0;

const normalizeHoldAfterMs = (value: unknown): number =>
  clamp(Math.round(normalizeNumber(value, DEFAULT_HOLD_AFTER_MS)), MIN_HOLD_AFTER_MS, MAX_HOLD_AFTER_MS);

const resolveAudioStatus = (item: Partial<TimelineItem>): AudioStatus => {
  if (item.audioStatus === "stale" || item.audioStatus === "generating" || item.audioStatus === "error") {
    return item.audioStatus;
  }
  return hasReadyAudioData(item) ? "ready" : "missing";
};

const revokeTimelineAudioUrls = (items: TimelineItem[]): void => {
  items.forEach((item) => {
    if (!item.audioUrl) return;
    try {
      URL.revokeObjectURL(item.audioUrl);
    } catch {
      // ignore
    }
  });
};

const markTimelineAudioStaleForVoiceConfig = (timeline: TimelineItem[]): TimelineItem[] =>
  timeline.map((item, index) => {
    const hasNarration = !!item.scriptItem?.voiceover_text?.trim();
    const nextItem = normalizeTimelineItem(
      {
        ...item,
        audioBlob: undefined,
        audioDuration: undefined,
        audioUrl: undefined,
        audioStatus: hasNarration ? "stale" : "missing",
      },
      index
    );
    return nextItem;
  });

const normalizeTimelineItem = (item: TimelineItem, index: number): TimelineItem => {
  const scriptBaseline = item.scriptBaseline ?? item.scriptItem?.voiceover_text ?? "";
  const scriptSource = item.scriptSource ?? {
    panelId: item.panelId,
    orderIndex: index,
  };
  const scriptStatus = item.scriptStatus ?? "auto";
  const enabled = item.enabled ?? true;
  const holdAfterMs = normalizeHoldAfterMs(item.holdAfterMs);
  const scriptSegment = item.scriptSegment ?? {
    narration: item.scriptItem?.voiceover_text ?? "",
    status: scriptStatus,
  };
  const audioStatus = resolveAudioStatus(item);
  const readyAudioBlob = hasReadyAudioData(item) ? item.audioBlob : undefined;
  const audioUrl = readyAudioBlob ? URL.createObjectURL(readyAudioBlob) : undefined;

  return {
    ...item,
    scriptBaseline,
    scriptSource,
    scriptSegment,
    scriptStatus,
    enabled,
    holdAfterMs,
    audioStatus,
    audioUrl,
  };
};

const hydrateLog = (log: Partial<GeminiLog> & Pick<GeminiLog, "type" | "message">, index: number): GeminiLog => ({
  ...log,
  id: log.id || `log-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`,
  timestamp: log.timestamp || new Date().toISOString(),
});

export const useRecapStore = create<RecapState>()(
  persist(
    (set, getStore) => ({
      config: normalizeAppConfig(),
      setConfig: (config) =>
        set((state) => ({
          config: normalizeAppConfig({ ...state.config, ...config }),
        })),

      voiceConfig: normalizeVoiceConfig(),
      setVoiceConfig: (config) =>
        set((state) => {
          const nextVoiceConfig = normalizeVoiceConfig({ ...state.voiceConfig, ...config });
          const voiceConfigChanged =
            nextVoiceConfig.provider !== state.voiceConfig.provider ||
            nextVoiceConfig.voiceKey !== state.voiceConfig.voiceKey ||
            nextVoiceConfig.speed !== state.voiceConfig.speed;

          if (!voiceConfigChanged) {
            return { voiceConfig: nextVoiceConfig };
          }

          revokeTimelineAudioUrls(state.timeline);
          const nextTimeline = markTimelineAudioStaleForVoiceConfig(state.timeline);
          void idbSet("recap-timeline-data", nextTimeline);

          return {
            voiceConfig: nextVoiceConfig,
            timeline: nextTimeline,
          };
        }),

      currentStep: "upload",
      setCurrentStep: (step) => set({ currentStep: step }),
      isLoading: false,
      setIsLoading: (loading) => set({ isLoading: loading }),
      progress: 0,
      setProgress: (progress) => set({ progress }),
      currentVoiceGeneration: null,
      setCurrentVoiceGeneration: (currentVoiceGeneration) => set({ currentVoiceGeneration }),

      aspectRatio: DEFAULT_ASPECT,
      setAspectRatio: (aspectRatio) =>
        set((state) => ({
          aspectRatio,
          renderConfig: normalizeRenderConfig({ ...state.renderConfig, aspectRatio }, aspectRatio),
        })),
      renderConfig: normalizeRenderConfig(undefined, DEFAULT_ASPECT),
      setRenderConfig: (config) =>
        set((state) => ({
          renderConfig: normalizeRenderConfig({ ...state.renderConfig, ...config }, state.aspectRatio),
        })),

      logs: [],
      addLog: (log) =>
        set((state) => ({
          logs: [...state.logs, hydrateLog(log, state.logs.length)].slice(-100),
        })),
      replaceLogs: (logs) =>
        set((state) => {
          const nextLogs = logs.map((log, index) => hydrateLog(log, index)).slice(-100);
          const isSame =
            state.logs.length === nextLogs.length &&
            state.logs.every(
              (log, index) =>
                log.id === nextLogs[index]?.id &&
                log.timestamp === nextLogs[index]?.timestamp &&
                log.type === nextLogs[index]?.type &&
                log.message === nextLogs[index]?.message &&
                log.details === nextLogs[index]?.details
            );
          return isSame ? state : { logs: nextLogs };
        }),
      clearLogs: () => set({ logs: [] }),


      virtualStrip: [],
      totalVirtualHeight: 0,
      stripWidth: STRIP_WIDTH,
      setVirtualStrip: (virtualStrip, totalVirtualHeight, stripWidth) => {
        getStore().virtualStrip.forEach((img) => {
          try {
            URL.revokeObjectURL(img.objectUrl);
          } catch {
            // ignore
          }
        });

        set({ virtualStrip, totalVirtualHeight, stripWidth });
        const persisted: PersistedVirtualStripState = {
          stripWidth,
          totalVirtualHeight,
          images: virtualStrip.map((image) => ({
            id: image.id,
            file: image.file,
            originalWidth: image.originalWidth,
            originalHeight: image.originalHeight,
            scaledHeight: image.scaledHeight,
            globalY: image.globalY,
          })),
        };
        void idbSet("recap-virtual-strip-data", persisted);
      },

      scenes: [],
      setScenes: (scenes) =>
        set((state) => ({
          scenes: scenes.map((scene) => normalizeSceneRect(scene, state.stripWidth)),
        })),
      updateScene: (id, updates) =>
        set((state) => ({
          scenes: state.scenes.map((scene) =>
            scene.id === id ? normalizeSceneRect({ ...scene, ...updates }, state.stripWidth) : scene
          ),
        })),
      addScene: (scene) =>
        set((state) => {
          const normalized = normalizeSceneRect(scene, state.stripWidth);
          return {
            scenes: [...state.scenes, normalized].sort((left, right) => left.y - right.y),
          };
        }),
      removeScene: (id) =>
        set((state) => ({
          scenes: state.scenes.filter((scene) => scene.id !== id),
        })),

      panels: [],
      setPanels: (panels) => {
        set((state) => {
          const nextSignature = buildPanelSignature(panels);
          const prevSignature = buildPanelSignature(state.panels);
          const signatureChanged = prevSignature !== nextSignature;

          return {
            panels,
            characterState: signatureChanged ? null : state.characterState,
            panelUnderstandings: signatureChanged ? [] : state.panelUnderstandings,
            panelUnderstandingMeta: signatureChanged ? EMPTY_PANEL_UNDERSTANDING_META : state.panelUnderstandingMeta,
            storyMemories: signatureChanged ? [] : state.storyMemories,
            scriptContext: signatureChanged
              ? { ...state.scriptContext, chapterId: "", characterContext: null }
              : state.scriptContext,
            scriptMeta:
              state.timeline.length > 0 && signatureChanged
                ? {
                    ...state.scriptMeta,
                    status: "outdated",
                    outdatedReason: "Panels changed after script generation.",
                  }
                : state.scriptMeta,
          };
        });
        void idbSet("recap-panels-data", panels);
      },
      addPanels: (newPanels) => {
        const updated = [...getStore().panels, ...newPanels];
        set({ panels: updated });
        void idbSet("recap-panels-data", updated);
      },

      scriptContext: {
        mangaName: "",
        mainCharacter: "",
        summary: "",
        language: "vi",
        chapterId: "",
        characterContext: null,
      },
      setScriptContext: (context) =>
        set((state) => ({
          scriptContext: { ...state.scriptContext, ...context },
        })),
      characterState: null,
      setCharacterState: (characterState) =>
        set((state) => ({
          characterState,
          scriptContext: {
            ...state.scriptContext,
            chapterId: characterState?.chapterId || "",
            characterContext: buildCharacterScriptContext(characterState),
          },
        })),
      clearCharacterState: () =>
        set((state) => ({
          characterState: null,
          scriptContext: {
            ...state.scriptContext,
            chapterId: "",
            characterContext: null,
          },
        })),
      panelUnderstandings: [],
      setPanelUnderstandings: (items) =>
        set((state) => ({
          panelUnderstandings: items.map((item, index) => normalizePanelUnderstanding(item, item.panelId, index)),
          panelUnderstandingMeta: {
            ...state.panelUnderstandingMeta,
            panelSignature: buildPanelSignature(state.panels),
          },
        })),
      panelUnderstandingMeta: EMPTY_PANEL_UNDERSTANDING_META,
      setPanelUnderstandingMeta: (panelUnderstandingMeta) => set({ panelUnderstandingMeta }),
      storyMemories: [],
      setStoryMemories: (storyMemories) => set({ storyMemories }),

      timeline: [],
      setTimeline: (timeline) => {
        const normalizedTimeline = timeline.map(normalizeTimelineItem);
        revokeTimelineAudioUrls(getStore().timeline);
        set({ timeline: normalizedTimeline });
        void idbSet("recap-timeline-data", normalizedTimeline);
      },
      updateTimelineItem: (index, item) => {
        const state = getStore();
        const newTimeline = [...state.timeline];
        const currentItem = newTimeline[index];
        if (!currentItem) return;
        const nextItem = normalizeTimelineItem({ ...currentItem, ...item }, index);
        const scriptChanged =
          !!item.scriptItem &&
          JSON.stringify(item.scriptItem) !== JSON.stringify(currentItem?.scriptItem);

        if (scriptChanged) {
          nextItem.scriptStatus = "edited";
          nextItem.scriptSegment = {
            narration: nextItem.scriptItem.voiceover_text ?? "",
            status: "edited",
          };
          delete nextItem.audioBlob;
          delete nextItem.audioDuration;
          delete nextItem.audioUrl;
          nextItem.audioStatus = nextItem.scriptItem.voiceover_text.trim() ? "stale" : "missing";
        }

        if (currentItem.audioUrl && currentItem.audioUrl !== nextItem.audioUrl) {
          try {
            URL.revokeObjectURL(currentItem.audioUrl);
          } catch {
            // ignore
          }
        }

        newTimeline[index] = nextItem;
        set({
          timeline: newTimeline,
          scriptMeta: scriptChanged
            ? {
                ...state.scriptMeta,
                status: "edited",
                outdatedReason: undefined,
              }
            : state.scriptMeta,
        });
        void idbSet("recap-timeline-data", newTimeline);
      },
      moveTimelineItem: (fromIndex, toIndex) => {
        const state = getStore();
        if (
          fromIndex < 0 ||
          toIndex < 0 ||
          fromIndex >= state.timeline.length ||
          toIndex >= state.timeline.length ||
          fromIndex === toIndex
        ) {
          return;
        }

        const nextTimeline = [...state.timeline];
        const [moved] = nextTimeline.splice(fromIndex, 1);
        nextTimeline.splice(toIndex, 0, moved);
        const normalizedTimeline = nextTimeline.map(normalizeTimelineItem);
        revokeTimelineAudioUrls(state.timeline);
        set({ timeline: normalizedTimeline });
        void idbSet("recap-timeline-data", normalizedTimeline);
      },
      removeTimelineItem: (index) => {
        const state = getStore();
        if (index < 0 || index >= state.timeline.length) return;

        const removedItem = state.timeline[index];
        if (removedItem?.audioUrl) {
          try {
            URL.revokeObjectURL(removedItem.audioUrl);
          } catch {
            // ignore
          }
        }

        const nextTimeline = state.timeline.filter((_, timelineIndex) => timelineIndex !== index);
        const normalizedTimeline = nextTimeline.map(normalizeTimelineItem);
        set({ timeline: normalizedTimeline });
        void idbSet("recap-timeline-data", normalizedTimeline);
      },
      duplicateTimelineItem: (index) => {
        const state = getStore();
        const currentItem = state.timeline[index];
        if (!currentItem) return;

        const duplicate: TimelineItem = {
          ...currentItem,
          audioBlob: undefined,
          audioDuration: undefined,
          audioUrl: undefined,
          audioStatus: currentItem.scriptItem.voiceover_text.trim() ? "stale" : "missing",
        };

        const nextTimeline = [...state.timeline];
        nextTimeline.splice(index + 1, 0, duplicate);
        const normalizedTimeline = nextTimeline.map(normalizeTimelineItem);
        set({
          timeline: normalizedTimeline,
          scriptMeta: {
            ...state.scriptMeta,
            status: "edited",
            outdatedReason: undefined,
          },
        });
        void idbSet("recap-timeline-data", normalizedTimeline);
      },
      resetTimelineItemToAuto: (index) => {
        const state = getStore();
        const currentItem = state.timeline[index];
        if (!currentItem) return;

        const baselineText = currentItem.scriptBaseline ?? "";
        const nextItem = normalizeTimelineItem(
          {
            ...currentItem,
            scriptItem: {
              ...currentItem.scriptItem,
              voiceover_text: baselineText,
            },
            scriptSegment: {
              narration: baselineText,
              status: "auto",
              memorySnapshot: currentItem.scriptSegment?.memorySnapshot,
            },
            scriptStatus: "auto",
            audioBlob: undefined,
            audioDuration: undefined,
            audioUrl: undefined,
            audioStatus: baselineText.trim() ? "missing" : "missing",
          },
          index
        );

        if (currentItem.audioUrl && currentItem.audioUrl !== nextItem.audioUrl) {
          try {
            URL.revokeObjectURL(currentItem.audioUrl);
          } catch {
            // ignore
          }
        }

        const nextTimeline = [...state.timeline];
        nextTimeline[index] = nextItem;
        set({
          timeline: nextTimeline,
          scriptMeta: {
            ...state.scriptMeta,
            status: nextTimeline.some((item) => item.scriptStatus === "edited") ? "edited" : "generated",
            outdatedReason: undefined,
          },
        });
        void idbSet("recap-timeline-data", nextTimeline);
      },
      scriptMeta: EMPTY_SCRIPT_META,
      setScriptMeta: (scriptMeta) => set({ scriptMeta }),
      markScriptOutdated: (reason) =>
        set((state) => ({
          scriptMeta:
            state.timeline.length > 0
              ? {
                  ...state.scriptMeta,
                  status: "outdated",
                  outdatedReason: reason,
                }
              : state.scriptMeta,
        })),
      clearScriptData: () => {
        revokeTimelineAudioUrls(getStore().timeline);
        set({
          panelUnderstandings: [],
          panelUnderstandingMeta: EMPTY_PANEL_UNDERSTANDING_META,
          storyMemories: [],
          timeline: [],
          scriptMeta: EMPTY_SCRIPT_META,
        });
        void idbSet("recap-timeline-data", []);
      },
      benchmarkRecords: [],
      addBenchmarkRecord: (record) =>
        set((state) => ({
          benchmarkRecords: [record, ...state.benchmarkRecords].slice(0, 30),
        })),
      removeBenchmarkRecord: (id) =>
        set((state) => ({
          benchmarkRecords: state.benchmarkRecords.filter((record) => record.id !== id),
        })),

      init: async () => {
        set((state) => ({
          config: normalizeAppConfig(state.config),
          voiceConfig: normalizeVoiceConfig(state.voiceConfig),
          renderConfig: normalizeRenderConfig(state.renderConfig, state.aspectRatio),
        }));

        const savedVirtualStrip = await get("recap-virtual-strip-data");
        if (savedVirtualStrip) {
          const parsed = savedVirtualStrip as PersistedVirtualStripState;
          const restoredImages: VirtualStripImage[] = parsed.images.map((image) => ({
            ...image,
            objectUrl: URL.createObjectURL(image.file),
          }));

          set({
            virtualStrip: restoredImages,
            totalVirtualHeight: parsed.totalVirtualHeight,
            stripWidth: parsed.stripWidth || STRIP_WIDTH,
          });
        } else if (getStore().currentStep === "extract") {
          set({ currentStep: "upload" });
        }

        const savedPanels = await get("recap-panels-data");
        if (savedPanels) {
          set({ panels: savedPanels as Panel[] });
        }
        const savedTimeline = await get("recap-timeline-data");
        if (savedTimeline) {
          set({ timeline: (savedTimeline as TimelineItem[]).map(normalizeTimelineItem) });
        }
      },

      reset: () => {
        getStore().virtualStrip.forEach((img) => {
          try {
            URL.revokeObjectURL(img.objectUrl);
          } catch {
            // ignore
          }
        });
        revokeTimelineAudioUrls(getStore().timeline);

        set({
          currentStep: "upload",
          virtualStrip: [],
          totalVirtualHeight: 0,
          stripWidth: STRIP_WIDTH,
          scenes: [],
          panels: [],
          panelUnderstandings: [],
          panelUnderstandingMeta: EMPTY_PANEL_UNDERSTANDING_META,
          storyMemories: [],
          timeline: [],
          scriptMeta: EMPTY_SCRIPT_META,
          scriptContext: { mangaName: "", mainCharacter: "", summary: "", language: "vi", chapterId: "", characterContext: null },
          characterState: null,
          benchmarkRecords: getStore().benchmarkRecords,
          progress: 0,
          currentVoiceGeneration: null,
          isLoading: false,
          logs: [],
          renderConfig: normalizeRenderConfig(undefined, DEFAULT_ASPECT),
        });
        void idbSet("recap-virtual-strip-data", null);
        void idbSet("recap-panels-data", []);
        void idbSet("recap-timeline-data", []);
      },
    }),
    {
      name: "manga-recap-storage-v11",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        config: normalizeAppConfig(state.config),
        voiceConfig: normalizeVoiceConfig(state.voiceConfig),
        currentStep: state.currentStep,
        stripWidth: state.stripWidth,
        scenes: state.scenes,
        panelUnderstandings: state.panelUnderstandings,
        panelUnderstandingMeta: state.panelUnderstandingMeta,
        storyMemories: state.storyMemories,
        scriptMeta: state.scriptMeta,
        scriptContext: state.scriptContext,
        characterState: state.characterState,
        logs: state.logs,
        aspectRatio: state.aspectRatio,
        benchmarkRecords: state.benchmarkRecords,
        renderConfig: normalizeRenderConfig(state.renderConfig, state.aspectRatio),
      }),
    }
  )
);
