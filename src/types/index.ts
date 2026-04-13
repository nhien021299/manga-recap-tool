// Core data interfaces
export const STRIP_WIDTH = 1080;
export const DEFAULT_ASPECT = 9 / 16;

export interface VirtualStripImage {
  id: string;
  file: File;
  originalWidth: number;
  originalHeight: number;
  scaledHeight: number;
  globalY: number;
  objectUrl: string;
}

export interface SafeBreakpoint {
  globalY: number;
  sourceImageId: string;
}

export interface Scene {
  id: string;
  y: number;
  height: number;
  isAuto: boolean;
}
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

export interface SFXItem {
  file: string;
  emoji: string;
}

export interface ScriptContext {
  mangaName: string;
  mainCharacter: string;
  summary?: string;
}

export interface ScriptItem {
  panel_index: number;
  ai_view: string;           // Mô tả ngắn gọn bối cảnh ẩn trong ảnh (dành cho Editor)
  voiceover_text: string;    // Đã gộp toàn bộ Lời dẫn + Thoại + Từ nối
  sfx: string[];             // Mảng các keyword âm thanh
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

export type LogType = 'request' | 'result' | 'error';
export interface GeminiLog {
  id: string;
  type: LogType;
  message: string;
  timestamp: string;
  details?: string;
}
