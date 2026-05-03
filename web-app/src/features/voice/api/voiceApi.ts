import type { VoiceGenerateRequest, VoiceOptionsResponse, TtsChunk } from "@/shared/types";

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
): Promise<{ blob: Blob; chunks?: TtsChunk[] }> {
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

  const blob = await response.blob();
  let chunks: TtsChunk[] | undefined;
  
  try {
    const chunksHeader = response.headers.get("X-TTS-Chunks");
    if (chunksHeader) {
      chunks = JSON.parse(decodeURIComponent(chunksHeader));
    }
  } catch (e) {
    console.error("Failed to parse TTS chunks header", e);
  }

  return { blob, chunks };
}
