import type { VoiceGenerateRequest, VoiceOptionsResponse } from "@/shared/types";

const buildUrl = (apiBaseUrl: string, path: string): string =>
  `${apiBaseUrl.replace(/\/$/, "")}${path}`;

export const resolveVoiceSampleUrl = (apiBaseUrl: string, sampleUrl?: string | null): string | null => {
  if (!sampleUrl) return null;
  if (/^https?:\/\//i.test(sampleUrl)) return sampleUrl;
  if (!sampleUrl.startsWith("/")) return buildUrl(apiBaseUrl, `/${sampleUrl}`);
  return buildUrl(apiBaseUrl, sampleUrl);
};

const readErrorMessage = async (response: Response): Promise<string> => {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || "Voice request failed.";
  }

  const text = await response.text();
  return text || "Voice request failed.";
};

export async function fetchVoiceOptions(apiBaseUrl: string): Promise<VoiceOptionsResponse> {
  const response = await fetch(buildUrl(apiBaseUrl, "/api/v1/voice/options"));
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return (await response.json()) as VoiceOptionsResponse;
}

export async function generateVoiceAudio(
  apiBaseUrl: string,
  request: VoiceGenerateRequest
): Promise<Blob> {
  const response = await fetch(buildUrl(apiBaseUrl, "/api/v1/voice/generate"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "audio/wav",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return await response.blob();
}
