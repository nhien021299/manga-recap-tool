// Core data interfaces
export interface Panel {
  id: string;
  blob: Blob;
  base64: string;           // compressed for LLM
  thumbnail: string;        // small preview URL
  width: number;
  height: number;
  order: number;
  originalImageRef?: string; // Blob URL of the upload image
  rect?: { x: number; y: number; width: number; height: number };
}

export interface ScriptContext {
  mangaName: string;
  mainCharacter: string;
  summary?: string;
}

export interface ScriptItem {
  panel_index: number;
  scene_description: string;
  speaker: string;
  dialogue: string;
  sfx: string;
}

export interface TimelineItem {
  panelId: string;
  imageBlob: Blob;
  scriptItem: ScriptItem;
  audioBlob?: Blob;
  audioDuration?: number;
  audioUrl?: string;        // BlobURL for preview
}

export interface AppConfig {
  geminiApiKey: string;
  elevenLabsApiKey: string;
  ttsVoiceId: string;
  ttsModel: string;
  language: 'vi' | 'en';
}

export type Step = 'upload' | 'extract' | 'script' | 'voice' | 'render';
