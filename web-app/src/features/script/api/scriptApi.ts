import type {
  Panel,
  ScriptContext,
  ScriptJobResult,
  ScriptJobStatusResponse,
} from "@/shared/types";

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

const buildFormData = (
  panels: Panel[],
  context: ScriptContext,
  options?: { reuseCache?: boolean; returnRawOutputs?: boolean }
) => {
  const formData = new FormData();
  formData.append(
    "context",
    JSON.stringify({
      mangaName: context.mangaName,
      mainCharacter: context.mainCharacter,
      summary: context.summary || "",
      language: context.language === "en" ? "en" : "vi",
    })
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

export async function createScriptJob(
  apiBaseUrl: string,
  panels: Panel[],
  context: ScriptContext,
  options?: { reuseCache?: boolean; returnRawOutputs?: boolean }
): Promise<{ jobId: string; status: string }> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/script/jobs`, {
    method: "POST",
    body: buildFormData(panels, context, options),
  });
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }
  return response.json();
}

export async function getScriptJobStatus(
  apiBaseUrl: string,
  jobId: string
): Promise<ScriptJobStatusResponse> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/script/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }
  return response.json();
}

export async function getScriptJobResult(
  apiBaseUrl: string,
  jobId: string
): Promise<ScriptJobResult> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/script/jobs/${jobId}/result`);
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }
  return response.json();
}

export async function cancelScriptJob(
  apiBaseUrl: string,
  jobId: string
): Promise<ScriptJobStatusResponse> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/script/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }
  return response.json();
}
