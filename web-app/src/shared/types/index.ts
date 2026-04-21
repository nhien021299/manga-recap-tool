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

export interface ScriptContext {
  mangaName?: string;
  mainCharacter?: string;
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
  voiceover_text: string;
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
export type ScriptPipeline = "backend-gemini-unified";

export interface StoryMemory {
  chunkIndex: number;
  summary: string;
  recentNames?: string[];
}

export interface ScriptMeta {
  status: ScriptDraftStatus;
  sourceUnits: ScriptSourceUnit[];
  generatedAt?: string;
  outdatedReason?: string;
  rawOutput?: string;
  pipeline?: ScriptPipeline;
  metrics?: Metrics;
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

export type TTSProvider = string;

export interface VoiceConfig {
  provider: TTSProvider;
  voiceKey: string;
  speed: number;
}

export interface VoiceOption {
  key: string;
  label: string;
  provider: TTSProvider;
  isAvailable: boolean;
  sampleRate?: number | null;
  speakerCount: number;
  quality: string;
  description: string;
  styleTag?: string | null;
  sampleUrl?: string | null;
  statusMessage?: string | null;
}

export interface VoiceProviderOption {
  id: TTSProvider;
  label: string;
  enabled: boolean;
  defaultVoiceKey?: string | null;
  statusMessage?: string | null;
  voices: VoiceOption[];
}

export interface VoiceOptionsResponse {
  defaultProvider: TTSProvider;
  providers: VoiceProviderOption[];
}

export interface VoiceGenerateRequest {
  text: string;
  provider: TTSProvider;
  voiceKey: string;
  speed: number;
}

export interface BenchmarkDimensionScore {
  key: string;
  label: string;
  score: number;
  note: string;
}

export interface BenchmarkRecord {
  id: string;
  title: string;
  createdAt: string;
  mangaName?: string;
  panelCount: number;
  mergedVoiceoverText: string;
  completionLogText: string;
  combinedText: string;
  metrics: Metrics;
  overallScore: number;
  grade: "A" | "B" | "C" | "D";
  dimensionScores: BenchmarkDimensionScore[];
  highlights: string[];
  warnings: string[];
}

export type Step = "upload" | "extract" | "script" | "voice" | "render" | "benchmark";
export type LogType = "request" | "result" | "error";

export interface GeminiLog {
  id: string;
  type: LogType;
  message: string;
  timestamp: string;
  details?: string;
}

export interface RawOutputs {
  understanding?: string;
  script?: string;
}

export interface Metrics {
  panelCount: number;
  totalMs: number;
  captionMs: number;
  ocrMs: number;
  mergeMs: number;
  scriptMs: number;
  avgPanelMs: number;
  captionSource: string;
  totalPromptTokens: number;
  totalCandidatesTokens: number;
  totalTokens: number;
  batchSizeUsed: number;
  retryCount: number;
  rateLimitedCount: number;
  throttleWaitMs: number;
  identityOcrMs: number;
  identityConfirmedCount: number;
}

export interface ScriptJobResult {
  understandings: PanelUnderstanding[];
  generatedItems: ScriptItem[];
  storyMemories: StoryMemory[];
  panelSignature: string;
  rawOutputs?: RawOutputs | null;
  metrics: Metrics;
}

export interface ScriptGenerationResponse {
  result: ScriptJobResult | null;
  logs: GeminiLog[];
  error?: string | null;
}
