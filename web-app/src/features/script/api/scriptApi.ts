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

export async function generateScriptViaBackend(
  apiBaseUrl: string,
  panels: Panel[],
  context: ScriptContext,
  options?: { reuseCache?: boolean; returnRawOutputs?: boolean }
): Promise<ScriptGenerationResponse> {
  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}/api/v1/script/generate`, {
    method: "POST",
    body: buildFormData(panels, context, options),
  });

  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }

  return response.json();
}
