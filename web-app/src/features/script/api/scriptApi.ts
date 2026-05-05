import type { Panel, ScriptContext, ScriptGenerationResponse } from "@/shared/types";

const normalizeBaseUrl = (value: string): string => value.trim().replace(/\/+$/, "");

const parseResponseError = async (response: Response): Promise<string> => {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const data = await response.json();
    return data.error || data.message || data.detail || `HTTP ${response.status}`;
  }
  const text = await response.text();
  return text || `HTTP ${response.status}`;
};

const parseFetchError = (error: unknown, apiBaseUrl: string): Error => {
  if (error instanceof Error && error.name === "AbortError") {
    return error;
  }
  if (error instanceof TypeError) {
    return new Error(
      `Cannot reach backend at ${normalizeBaseUrl(
        apiBaseUrl
      )}. Check that the backend is running and that CORS allows this web origin.`
    );
  }
  return error instanceof Error ? error : new Error("Unknown network error.");
};

const buildFormData = (
  panels: Panel[],
  context: ScriptContext,
  options?: { reuseCache?: boolean; returnRawOutputs?: boolean }
) => {
  const formData = new FormData();
  const payload: Record<string, unknown> = {
    language: context.language === "en" ? "en" : "vi",
  };
  const mangaName = context.mangaName?.trim();
  const mainCharacter = context.mainCharacter?.trim();
  const summary = context.summary?.trim();
  const chapterId = context.chapterId?.trim();

  if (mangaName) payload.mangaName = mangaName;
  if (mainCharacter) payload.mainCharacter = mainCharacter;
  if (summary) payload.summary = summary;
  if (chapterId) payload.chapterId = chapterId;
  if (context.characterContext) payload.characterContext = context.characterContext;

  formData.append(
    "context",
    JSON.stringify(payload)
  );
  formData.append(
    "panels",
    JSON.stringify(
      panels.map((panel) => ({
        panelId: panel.id,
        orderIndex: panel.order,
      }))
    )
  );
  formData.append(
    "options",
    JSON.stringify({
      reuseCache: options?.reuseCache ?? true,
      returnRawOutputs: options?.returnRawOutputs ?? true,
    })
  );
  panels.forEach((panel, index) => {
    formData.append("files", panel.blob, `panel-${index + 1}.png`);
  });
  return formData;
};

export async function submitScriptGeneration(
  apiBaseUrl: string,
  panels: Panel[],
  context: ScriptContext,
  options?: { reuseCache?: boolean; returnRawOutputs?: boolean }
) : Promise<ScriptGenerationResponse> {
  try {
    const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/script/generate`, {
      method: "POST",
      body: buildFormData(panels, context, options),
    });

    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return response.json();
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}

// ---------------------------------------------------------------------------
// Narration upload + video production
// ---------------------------------------------------------------------------

export interface NarrationScene {
  scene: number;
  title: string;
  narration: string;
  duration_seconds: number;
  dialogue?: string | null;
  dialogue_speaker?: string | null;
  dialogue_timing?: string | null;
  // Effect metadata
  scene_type?: string;
  mood?: string;
  motion_preset?: string;
  motion_intensity?: number;
  transition?: string;
  transition_duration_ms?: number;
  vfx_tags?: string[];
  sfx_tags?: string[];
  subtitle_mood?: string;
}

export interface NarrationPayload {
  project?: string;
  chapter?: number;
  language?: string;
  scenes: NarrationScene[];
}

export interface EffectSuggestion {
  scene: number;
  scene_type: string;
  mood: string;
  motion_preset: string;
  motion_intensity: number;
  transition: string;
  transition_duration_ms: number;
  vfx_tags: string[];
  sfx_tags: string[];
  subtitle_mood?: string | null;
}

export interface EffectSuggestionResponse {
  scenes: EffectSuggestion[];
}

export interface VideoJobStatus {
  job_id: string;
  phase: string;
  progress: number;
  detail: string;
  error?: string | null;
  download_url?: string | null;
}

/**
 * Upload narration JSON + panel images to kick off the full
 * TTS → Gemini direction → Remotion render pipeline.
 */
export async function submitNarrationProduction(
  apiBaseUrl: string,
  narration: NarrationPayload,
  panels: Panel[],
  voiceConfig?: { voiceKey?: string; speed?: number; provider?: string },
  directionData?: any,
  audioBlobs?: { scene: number; blob: Blob }[]
): Promise<VideoJobStatus> {
  const base = normalizeBaseUrl(apiBaseUrl);
  const formData = new FormData();

  const narrationBlob = new Blob([JSON.stringify(narration)], { type: "application/json" });
  formData.append("narration_file", narrationBlob, "narration.json");
  
  formData.append("voice_key", voiceConfig?.voiceKey || "voice_default");
  formData.append("speed", String(voiceConfig?.speed ?? 1.15));
  formData.append("provider", voiceConfig?.provider || "vieneu");
  
  if (directionData) {
    const directionBlob = new Blob([JSON.stringify(directionData)], { type: "application/json" });
    formData.append("direction_file", directionBlob, "direction.json");
  }

  panels.forEach((panel, index) => {
    formData.append("files", panel.blob, `panel-${index + 1}.png`);
  });

  if (audioBlobs) {
    audioBlobs.forEach((item) => {
      formData.append("audio_files", item.blob, `scene_${item.scene}.wav`);
    });
  }

  try {
    const response = await fetch(`${base}/api/v1/video/produce-from-narration`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return response.json();
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}

/**
 * Poll the status of a video production job.
 */
export async function pollVideoJobStatus(
  apiBaseUrl: string,
  jobId: string,
): Promise<VideoJobStatus> {
  const base = normalizeBaseUrl(apiBaseUrl);
  try {
    const response = await fetch(`${base}/api/v1/video/jobs/${jobId}`);
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return response.json();
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}

/**
 * Cancel a running video production job.
 */
export async function cancelVideoJob(
  apiBaseUrl: string,
  jobId: string,
): Promise<VideoJobStatus> {
  const base = normalizeBaseUrl(apiBaseUrl);
  try {
    const response = await fetch(`${base}/api/v1/video/jobs/${jobId}/cancel`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return response.json();
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}

/**
 * Stop all running jobs and delete all temporary job files.
 */
export async function purgeVideoData(apiBaseUrl: string): Promise<any> {
  const base = normalizeBaseUrl(apiBaseUrl);
  try {
    const response = await fetch(`${base}/api/v1/video/jobs/purge`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return response.json();
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}

/**
 * Suggest cinematic effects for a narration package using Gemini.
 */
export async function suggestEffectMetadata(
  apiBaseUrl: string,
  scenes: NarrationScene[],
  style: string = "dark_xianxia_recap"
): Promise<EffectSuggestionResponse> {
  const base = normalizeBaseUrl(apiBaseUrl);
  try {
    const response = await fetch(`${base}/api/v1/video/suggest-effects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenes, style }),
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return response.json();
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}
