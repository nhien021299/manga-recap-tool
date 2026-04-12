import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { get, set as idbSet } from 'idb-keyval';
import type { Panel, TimelineItem, AppConfig, Step, ScriptContext } from '@/types';

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

  // Data
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

export const useRecapStore = create<RecapState>()(
  persist(
    (set, getStore) => ({
      // Config
      config: {
        geminiApiKey: 'AIzaSyDVZIkGsERdUoiJW-bsWodw44cgMQBCD1c',
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
      setTimeline: (timeline) => set({ timeline }),
      updateTimelineItem: (index, item) => set((state) => {
        const newTimeline = [...state.timeline];
        newTimeline[index] = { ...newTimeline[index], ...item };
        return { timeline: newTimeline };
      }),

      // Hydration
      init: async () => {
        const savedPanels = await get('recap-panels-data');
        if (savedPanels) {
          set({ panels: savedPanels as Panel[] });
        }
      },

      // Actions
      reset: () => {
        set({
          currentStep: 'upload',
          panels: [],
          timeline: [],
          scriptContext: { mangaName: '', mainCharacter: '', summary: '' },
          progress: 0,
          isLoading: false
        });
        idbSet('recap-panels-data', []);
      },
    }),
    {
      name: 'manga-recap-storage-v2',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ 
        config: state.config,
        currentStep: state.currentStep,
        scriptContext: state.scriptContext,
        // Panels are handled manually via IDB
      }),
    }
  )
);
