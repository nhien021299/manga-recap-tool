import type { RenderJobCreateResponse, RenderJobStatusResponse, RenderPlan, RenderRevealResponse } from "@/shared/types";

const normalizeBaseUrl = (value: string): string => value.trim().replace(/\/+$/, "");

const buildUrl = (apiBaseUrl: string, path: string): string => `${normalizeBaseUrl(apiBaseUrl)}${path}`;

const parseResponseError = async (response: Response): Promise<string> => {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const data = (await response.json()) as { error?: string; message?: string; detail?: string };
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
      `Cannot reach backend at ${normalizeBaseUrl(apiBaseUrl)}. Check that the backend is running and that CORS allows this web origin.`
    );
  }
  return error instanceof Error ? error : new Error("Unknown network error.");
};

const buildRenderFormData = (plan: RenderPlan): FormData => {
  const formData = new FormData();
  formData.append(
    "plan",
    JSON.stringify({
      outputWidth: plan.outputWidth,
      outputHeight: plan.outputHeight,
      captionMode: plan.captionMode,
      frameRate: plan.frameRate,
    })
  );
  formData.append(
    "clips",
    JSON.stringify(
      plan.clips.map((clip) => ({
        clipId: clip.clipId,
        panelId: clip.panelId,
        orderIndex: clip.orderIndex,
        durationMs: clip.durationMs,
        holdAfterMs: clip.holdAfterMs,
        captionText: clip.captionText,
        panelFileKey: clip.panelFileKey,
        audioFileKey: clip.audioFileKey ?? null,
        motionPreset: clip.motionPreset,
        motionSeed: clip.motionSeed,
        motionIntensity: clip.motionIntensity,
      }))
    )
  );

  plan.clips.forEach((clip) => {
    formData.append("files", clip.imageBlob, `${clip.panelFileKey}.png`);
    if (clip.audioBlob && clip.audioFileKey) {
      formData.append("files", clip.audioBlob, `${clip.audioFileKey}.wav`);
    }
  });

  return formData;
};

export const resolveRenderResultUrl = (apiBaseUrl: string, resultPath?: string | null): string | null => {
  if (!resultPath) return null;
  if (/^https?:\/\//i.test(resultPath)) return resultPath;
  return buildUrl(apiBaseUrl, resultPath.startsWith("/") ? resultPath : `/${resultPath}`);
};

export async function createRenderJob(apiBaseUrl: string, plan: RenderPlan): Promise<RenderJobCreateResponse> {
  try {
    const response = await fetch(buildUrl(apiBaseUrl, "/api/v1/render/jobs"), {
      method: "POST",
      body: buildRenderFormData(plan),
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return (await response.json()) as RenderJobCreateResponse;
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}

export async function fetchRenderJobStatus(
  apiBaseUrl: string,
  jobId: string
): Promise<RenderJobStatusResponse> {
  try {
    const response = await fetch(buildUrl(apiBaseUrl, `/api/v1/render/jobs/${jobId}`));
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return (await response.json()) as RenderJobStatusResponse;
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}

export async function cancelRenderJob(apiBaseUrl: string, jobId: string): Promise<RenderJobStatusResponse> {
  try {
    const response = await fetch(buildUrl(apiBaseUrl, `/api/v1/render/jobs/${jobId}/cancel`), {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return (await response.json()) as RenderJobStatusResponse;
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}

export async function revealRenderResult(apiBaseUrl: string, jobId: string): Promise<RenderRevealResponse> {
  try {
    const response = await fetch(buildUrl(apiBaseUrl, `/api/v1/render/jobs/${jobId}/reveal`), {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    return (await response.json()) as RenderRevealResponse;
  } catch (error) {
    throw parseFetchError(error, apiBaseUrl);
  }
}
