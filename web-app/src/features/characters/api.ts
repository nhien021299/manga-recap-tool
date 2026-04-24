import type { ChapterCharacterState, Panel } from "@/shared/types";

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

const buildPrepassFormData = (
  chapterId: string,
  panels: Panel[],
  options?: { force?: boolean }
): FormData => {
  const formData = new FormData();
  formData.append(
    "payload",
    JSON.stringify({
      chapterId,
      force: options?.force ?? false,
      panels: panels.map((panel) => ({
        panelId: panel.id,
        orderIndex: panel.order,
      })),
    })
  );
  panels.forEach((panel, index) => {
    formData.append("files", panel.blob, `panel-${index + 1}.png`);
  });
  return formData;
};

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }
  return response.json() as Promise<T>;
}

export async function runCharacterPrepass(
  apiBaseUrl: string,
  chapterId: string,
  panels: Panel[],
  options?: { force?: boolean }
): Promise<ChapterCharacterState> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/characters/prepass`, {
    method: "POST",
    body: buildPrepassFormData(chapterId, panels, options),
  });
  return parseJsonResponse<ChapterCharacterState>(response);
}

export async function createCharacterCluster(
  apiBaseUrl: string,
  payload: {
    chapterId: string;
    canonicalName?: string;
    displayLabel?: string;
    lockName?: boolean;
    cropIds?: string[];
    panelIds?: string[];
  }
): Promise<ChapterCharacterState> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/characters/clusters`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<ChapterCharacterState>(response);
}

export async function renameCharacterCluster(
  apiBaseUrl: string,
  payload: { chapterId: string; clusterId: string; canonicalName: string; lockName: boolean }
): Promise<ChapterCharacterState> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/characters/rename`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<ChapterCharacterState>(response);
}

export async function mergeCharacterClusters(
  apiBaseUrl: string,
  payload: { chapterId: string; sourceClusterId: string; targetClusterId: string }
): Promise<ChapterCharacterState> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/characters/merge`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<ChapterCharacterState>(response);
}

export async function splitCharacterCluster(
  apiBaseUrl: string,
  payload: {
    chapterId: string;
    sourceClusterId: string;
    cropIds?: string[];
    panelIds?: string[];
    canonicalName?: string;
  }
): Promise<ChapterCharacterState> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/characters/split`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<ChapterCharacterState>(response);
}

export async function updateCharacterPanelMapping(
  apiBaseUrl: string,
  payload: { chapterId: string; panelId: string; clusterIds: string[] }
): Promise<ChapterCharacterState> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/characters/panel-mapping`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<ChapterCharacterState>(response);
}

export async function updateCharacterCropMapping(
  apiBaseUrl: string,
  payload: { chapterId: string; cropId: string; clusterId?: string | null }
): Promise<ChapterCharacterState> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/characters/crop-mapping`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<ChapterCharacterState>(response);
}

export async function updateCharacterClusterStatus(
  apiBaseUrl: string,
  payload: { chapterId: string; clusterId: string; status: "draft" | "unknown" | "ignored" }
): Promise<ChapterCharacterState> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/characters/status`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<ChapterCharacterState>(response);
}
