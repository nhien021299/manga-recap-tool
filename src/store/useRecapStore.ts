import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { get, set as idbSet } from 'idb-keyval';
import type { Panel, TimelineItem, AppConfig, Step, ScriptContext, GeminiLog, SFXItem, VirtualStripImage, Scene } from '@/types';
import { DEFAULT_ASPECT, STRIP_WIDTH } from '@/types';

interface RecapState {
  // Config
  config: AppConfig;
  setConfig: (config: Partial<AppConfig>) => void;

  // UI State
  currentStep: Step;
  setCurrentStep: (step: Step) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  progress: number;
  setProgress: (progress: number) => void;

  // Video Settings
  aspectRatio: number;
  setAspectRatio: (ratio: number) => void;

  // Gemini Logs
  logs: GeminiLog[];
  addLog: (log: Omit<GeminiLog, 'id' | 'timestamp'>) => void;
  clearLogs: () => void;

  // Dictionary
  sfxDictionary: Record<string, SFXItem>;
  addSFXToDictionary: (sfxList: string[]) => void;

  // Image Flow (Virtual)
  virtualStrip: VirtualStripImage[];
  totalVirtualHeight: number;
  stripWidth: number;
  setVirtualStrip: (strip: VirtualStripImage[], totalHeight: number, stripWidth: number) => void;
  
  scenes: Scene[];
  setScenes: (scenes: Scene[]) => void;
  updateScene: (id: string, updates: Partial<Scene>) => void;
  addScene: (scene: Scene) => void;
  removeScene: (id: string) => void;

  // Data (Legacy/Final output)
  panels: Panel[];
  setPanels: (panels: Panel[]) => void;
  addPanels: (panels: Panel[]) => void;
  
  scriptContext: ScriptContext;
  setScriptContext: (context: Partial<ScriptContext>) => void;

  timeline: TimelineItem[];
  setTimeline: (timeline: TimelineItem[]) => void;
  updateTimelineItem: (index: number, item: Partial<TimelineItem>) => void;

  // Hydration
  init: () => Promise<void>;
  
  // Actions
  reset: () => void;
}

const normalizeSceneRect = (scene: Scene, stripWidth: number): Scene => {
  const x = Math.min(Math.max(scene.x ?? 0, 0), Math.max(0, stripWidth - 1));
  const width = Math.min(Math.max(scene.width ?? stripWidth, 1), Math.max(1, stripWidth - x));
  return { ...scene, x, width };
};

export const useRecapStore = create<RecapState>()(
  persist(
    (set, getStore) => ({
      // Config
      config: {
        geminiApiKey: import.meta.env.VITE_GEMINI_API_KEY || '',
        elevenLabsApiKey: '',
        ttsVoiceId: 'pNInz6obpgmqS29pXo3W', // Default Rachel
        ttsModel: 'eleven_multilingual_v2',
        language: 'vi',
      },
      setConfig: (config) => set((state) => ({ config: { ...state.config, ...config } })),

      // UI State
      currentStep: 'upload',
      setCurrentStep: (step) => set({ currentStep: step }),
      isLoading: false,
      setIsLoading: (loading) => set({ isLoading: loading }),
      progress: 0,
      setProgress: (progress) => set({ progress }),

      // Gemini Logs
      logs: [],
      addLog: (log) => set((state) => ({
        logs: [
          ...state.logs,
          {
            ...log,
            id: Math.random().toString(36).substring(7),
            timestamp: new Date().toLocaleTimeString(),
          }
        ].slice(-50), // Keep last 50 logs, newer at the bottom
      })),
      clearLogs: () => set({ logs: [] }),

      // Dictionary
      sfxDictionary: {
        "sấm sét": { file: "thunder_01.mp3", emoji: "🌩️" },
        "chém kiếm": { file: "sword_slash.mp3", emoji: "⚔️" },
      },
      addSFXToDictionary: (sfxList) => set((state) => {
        const newDict = { ...state.sfxDictionary };
        let updated = false;
        
        sfxList.forEach(sfx => {
          const key = sfx.toLowerCase().trim();
          if (!newDict[key]) {
            newDict[key] = { file: "", emoji: "🔔" }; // Default new SFX
            updated = true;
          }
        });
        
        return updated ? { sfxDictionary: newDict } : state;
      }),

      // Video Settings
      aspectRatio: DEFAULT_ASPECT,
      setAspectRatio: (aspectRatio) => set({ aspectRatio }),

      // Image Flow (Virtual)
      virtualStrip: [],
      totalVirtualHeight: 0,
      stripWidth: STRIP_WIDTH,
      setVirtualStrip: (virtualStrip, totalVirtualHeight, stripWidth) => set({ virtualStrip, totalVirtualHeight, stripWidth }),

      scenes: [],
      setScenes: (scenes) => set((state) => ({
        scenes: scenes.map((scene) => normalizeSceneRect(scene, state.stripWidth))
      })),
      updateScene: (id, updates) => set((state) => ({
        scenes: state.scenes.map((scene) => {
          if (scene.id !== id) return scene;
          return normalizeSceneRect({ ...scene, ...updates }, state.stripWidth);
        })
      })),
      addScene: (scene) => set((state) => {
        const normalized = normalizeSceneRect(scene, state.stripWidth);
        const newScenes = [...state.scenes, normalized].sort((a, b) => a.y - b.y);
        return { scenes: newScenes };
      }),
      removeScene: (id) => set((state) => ({
        scenes: state.scenes.filter(s => s.id !== id)
      })),

      // Data
      panels: [],
      setPanels: (panels) => {
        set({ panels });
        idbSet('recap-panels-data', panels); // Persist Blobs to IDB
      },
      addPanels: (newPanels) => {
        const updated = [...getStore().panels, ...newPanels];
        set({ panels: updated });
        idbSet('recap-panels-data', updated);
      },

      scriptContext: {
        mangaName: '',
        mainCharacter: '',
        summary: ''
      },
      setScriptContext: (context) => set((state) => ({ 
        scriptContext: { ...state.scriptContext, ...context } 
      })),

      timeline: [],
      setTimeline: (timeline) => {
        set({ timeline });
        idbSet('recap-timeline-data', timeline);
      },
      updateTimelineItem: (index, item) => {
        const state = getStore();
        const newTimeline = [...state.timeline];
        newTimeline[index] = { ...newTimeline[index], ...item };
        set({ timeline: newTimeline });
        idbSet('recap-timeline-data', newTimeline);
      },

      // Hydration
      init: async () => {
        const savedPanels = await get('recap-panels-data');
        if (savedPanels) {
          set({ panels: savedPanels as Panel[] });
        }
        const savedTimeline = await get('recap-timeline-data');
        if (savedTimeline) {
          set({ timeline: savedTimeline as TimelineItem[] });
        }
      },

      // Actions
      reset: () => {
        set({
          currentStep: 'upload',
          virtualStrip: [],
          totalVirtualHeight: 0,
          stripWidth: STRIP_WIDTH,
          scenes: [],
          panels: [],
          timeline: [],
          scriptContext: { mangaName: '', mainCharacter: '', summary: '' },
          progress: 0,
          isLoading: false,
          logs: []
        });
        idbSet('recap-panels-data', []);
        idbSet('recap-timeline-data', []);
      },
    }),
    {
      name: 'manga-recap-storage-v6',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ 
        config: state.config,
        currentStep: state.currentStep,
        scriptContext: state.scriptContext,
        logs: state.logs,
        sfxDictionary: state.sfxDictionary,
        aspectRatio: state.aspectRatio,
      }),
    }
  )
);
