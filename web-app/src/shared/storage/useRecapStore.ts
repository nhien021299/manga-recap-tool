import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { get, set as idbSet } from "idb-keyval";

import {
  DEFAULT_ASPECT,
  STRIP_WIDTH,
  type AppConfig,
  type GeminiLog,
  type Panel,
  type PanelUnderstanding,
  type PanelUnderstandingMeta,
  type SFXItem,
  type Scene,
  type ScriptContext,
  type ScriptMeta,
  type Step,
  type StoryMemory,
  type TimelineItem,
  type VirtualStripImage,
  type VoiceConfig,
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

  aspectRatio: number;
  setAspectRatio: (ratio: number) => void;

  logs: GeminiLog[];
  addLog: (log: Omit<GeminiLog, "id" | "timestamp">) => void;
  replaceLogs: (logs: GeminiLog[]) => void;
  clearLogs: () => void;

  sfxDictionary: Record<string, SFXItem>;
  addSFXToDictionary: (sfxList: string[]) => void;

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
  panelUnderstandings: PanelUnderstanding[];
  setPanelUnderstandings: (items: PanelUnderstanding[]) => void;
  panelUnderstandingMeta: PanelUnderstandingMeta;
  setPanelUnderstandingMeta: (meta: PanelUnderstandingMeta) => void;
  storyMemories: StoryMemory[];
  setStoryMemories: (items: StoryMemory[]) => void;

  timeline: TimelineItem[];
  setTimeline: (timeline: TimelineItem[]) => void;
  updateTimelineItem: (index: number, item: Partial<TimelineItem>) => void;
  scriptMeta: ScriptMeta;
  setScriptMeta: (meta: ScriptMeta) => void;
  markScriptOutdated: (reason: string) => void;
  clearScriptData: () => void;

  init: () => Promise<void>;
  reset: () => void;
}

type PersistedVirtualStripImage = Omit<VirtualStripImage, "objectUrl">;

interface PersistedVirtualStripState {
  stripWidth: number;
  totalVirtualHeight: number;
  images: PersistedVirtualStripImage[];
}

const normalizeSecret = (value: string | undefined | null): string => {
  if (!value) return "";
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
};

const normalizeAppConfig = (config?: Partial<AppConfig> | null): AppConfig => ({
  apiBaseUrl: (config?.apiBaseUrl || import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").trim(),
  language: config?.language === "en" ? "en" : "vi",
});

const normalizeVoiceConfig = (config?: Partial<VoiceConfig> | null): VoiceConfig => ({
  elevenLabsApiKey: normalizeSecret(config?.elevenLabsApiKey || import.meta.env.VITE_ELEVENLABS_API_KEY || ""),
  ttsVoiceId: (config?.ttsVoiceId || import.meta.env.VITE_TTS_VOICE_ID || "pNInz6obpgmqS29pXo3W").trim(),
  ttsModel: (config?.ttsModel || import.meta.env.VITE_TTS_MODEL || "eleven_multilingual_v2").trim(),
});

const EMPTY_SCRIPT_META: ScriptMeta = {
  status: "idle",
  sourceUnits: [],
  rawOutput: "",
  pipeline: "backend-gemini",
};

const EMPTY_PANEL_UNDERSTANDING_META: PanelUnderstandingMeta = {
  panelSignature: "",
  rawOutput: "",
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
  sfx: Array.isArray(item.sfx) ? item.sfx : [],
  cliffhanger: item.cliffhanger || "",
});

const normalizeTimelineItem = (item: TimelineItem, index: number): TimelineItem => {
  const scriptSource = item.scriptSource ?? {
    panelId: item.panelId,
    orderIndex: index,
  };
  const scriptStatus = item.scriptStatus ?? "auto";
  const scriptSegment = item.scriptSegment ?? {
    narration: item.scriptItem?.voiceover_text ?? "",
    status: scriptStatus,
  };

  return {
    ...item,
    scriptSource,
    scriptSegment,
    scriptStatus,
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
        set((state) => ({
          voiceConfig: normalizeVoiceConfig({ ...state.voiceConfig, ...config }),
        })),

      currentStep: "upload",
      setCurrentStep: (step) => set({ currentStep: step }),
      isLoading: false,
      setIsLoading: (loading) => set({ isLoading: loading }),
      progress: 0,
      setProgress: (progress) => set({ progress }),

      aspectRatio: DEFAULT_ASPECT,
      setAspectRatio: (aspectRatio) => set({ aspectRatio }),

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

      sfxDictionary: {
        "sấm sét": { file: "thunder_01.mp3", emoji: "🌩️" },
        "chém kiếm": { file: "sword_slash.mp3", emoji: "⚔️" },
      },
      addSFXToDictionary: (sfxList) =>
        set((state) => {
          const next = { ...state.sfxDictionary };
          let changed = false;
          sfxList.forEach((sfx) => {
            const key = sfx.toLowerCase().trim();
            if (key && !next[key]) {
              next[key] = { file: "", emoji: "🔔" };
              changed = true;
            }
          });
          return changed ? { sfxDictionary: next } : state;
        }),

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
          images: virtualStrip.map(({ objectUrl, ...rest }) => rest),
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
            panelUnderstandings: signatureChanged ? [] : state.panelUnderstandings,
            panelUnderstandingMeta: signatureChanged ? EMPTY_PANEL_UNDERSTANDING_META : state.panelUnderstandingMeta,
            storyMemories: signatureChanged ? [] : state.storyMemories,
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
      },
      setScriptContext: (context) =>
        set((state) => ({
          scriptContext: { ...state.scriptContext, ...context },
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
        set({ timeline: normalizedTimeline });
        void idbSet("recap-timeline-data", normalizedTimeline);
      },
      updateTimelineItem: (index, item) => {
        const state = getStore();
        const newTimeline = [...state.timeline];
        const currentItem = newTimeline[index];
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
        set({
          panelUnderstandings: [],
          panelUnderstandingMeta: EMPTY_PANEL_UNDERSTANDING_META,
          storyMemories: [],
          timeline: [],
          scriptMeta: EMPTY_SCRIPT_META,
        });
        void idbSet("recap-timeline-data", []);
      },

      init: async () => {
        set((state) => ({
          config: normalizeAppConfig(state.config),
          voiceConfig: normalizeVoiceConfig(state.voiceConfig),
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
          scriptContext: { mangaName: "", mainCharacter: "", summary: "", language: "vi" },
          progress: 0,
          isLoading: false,
          logs: [],
        });
        void idbSet("recap-virtual-strip-data", null);
        void idbSet("recap-panels-data", []);
        void idbSet("recap-timeline-data", []);
      },
    }),
    {
      name: "manga-recap-storage-v9",
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
        logs: state.logs,
        sfxDictionary: state.sfxDictionary,
        aspectRatio: state.aspectRatio,
      }),
    }
  )
);
