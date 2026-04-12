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
  ai_view: string;       // Mô tả ngắn gọn bối cảnh ẩn trong ảnh (dành cho Editor)
  speaker: string;       // Tên người nói hoặc [Biến số], trống nếu không ai nói
  dialogue: string;      // Lời thoại trực tiếp trong bong bóng chat (nếu có)
  narration: string;     // LỜI DẪN TRUYỆN CỦA MC. Kể lại diễn biến, phân tích tâm lý
  sfx: string;           // Tiếng động (Kếch, Rầm...) nếu có
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
