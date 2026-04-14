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

export interface Scene {
  id: string;
  x?: number;
  y: number;
  width?: number;
  height: number;
  isAuto: boolean;
  confidence?: number;
  boundaryLinked?: boolean;
  mergeCandidate?: boolean;
  splitCandidate?: boolean;
  failureModes?: string[];
}

export interface Panel {
  id: string;
  blob: Blob;
  base64: string;
  thumbnail: string;
  width: number;
  height: number;
  order: number;
  originalImageRef?: string;
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
  language?: "vi" | "en";
}

export interface PanelUnderstanding {
  panelId: string;
  orderIndex: number;
  summary: string;
  action: string;
  emotion: string;
  dialogue: string;
  sfx: string[];
  cliffhanger: string;
}

export interface PanelUnderstandingMeta {
  generatedAt?: string;
  panelSignature: string;
  rawOutput?: string;
}

export type SceneInput = PanelUnderstanding;

export interface ScriptItem {
  panel_index: number;
  ai_view: string;
  voiceover_text: string;
  sfx: string[];
}

export interface ScriptSourceUnit {
  panelId: string;
  orderIndex: number;
}

export interface ScriptSegment {
  narration: string;
  status: "auto" | "edited";
  memorySnapshot?: string;
}

export type ScriptDraftStatus = "idle" | "generated" | "edited" | "outdated";
export type ScriptPipeline = "two-stage" | "local-caption-memory" | "backend-caption-memory";
export type ScriptJobStatus = "idle" | "queued" | "running" | "completed" | "failed" | "cancelled";

export interface StoryMemory {
  chunkIndex: number;
  summary: string;
}

export interface ScriptMeta {
  status: ScriptDraftStatus;
  sourceUnits: ScriptSourceUnit[];
  generatedAt?: string;
  outdatedReason?: string;
  rawOutput?: string;
  pipeline?: ScriptPipeline;
}

export interface TimelineItem {
  panelId: string;
  imageBlob: Blob;
  scriptItem: ScriptItem;
  scriptSource?: ScriptSourceUnit;
  scriptSegment?: ScriptSegment;
  scriptStatus?: "auto" | "edited";
  audioBlob?: Blob;
  audioDuration?: number;
  audioUrl?: string;
}

export interface AppConfig {
  apiBaseUrl: string;
  language: "vi" | "en";
}

export interface VoiceConfig {
  elevenLabsApiKey: string;
  ttsVoiceId: string;
  ttsModel: string;
}

export type Step = "upload" | "extract" | "script" | "voice" | "render";
export type LogType = "request" | "result" | "error";

export interface GeminiLog {
  id: string;
  type: LogType;
  message: string;
  timestamp: string;
  details?: string;
}

export interface ScriptJobState {
  jobId?: string;
  status: ScriptJobStatus;
  progress: number;
  error?: string;
  resultReady?: boolean;
  lastSyncAt?: string;
}

export interface ScriptJobRequest {
  context: {
    mangaName: string;
    mainCharacter: string;
    summary?: string;
    language: "vi" | "en";
  };
  panels: Array<{
    panelId: string;
    orderIndex: number;
  }>;
  files: File[];
  options?: {
    reuseCache?: boolean;
    returnRawOutputs?: boolean;
  };
}

export interface ScriptJobMetrics {
  panelCount: number;
  totalMs: number;
  captionMs: number;
  scriptMs: number;
}

export interface ScriptJobResult {
  understandings: PanelUnderstanding[];
  generatedItems: ScriptItem[];
  storyMemories: StoryMemory[];
  panelSignature: string;
  rawOutputs?: {
    understanding: string;
    script: string;
  };
  metrics: ScriptJobMetrics;
}

export interface ScriptJobStatusResponse {
  jobId: string;
  status: Exclude<ScriptJobStatus, "idle">;
  progress: number;
  error?: string | null;
  logs: GeminiLog[];
}
