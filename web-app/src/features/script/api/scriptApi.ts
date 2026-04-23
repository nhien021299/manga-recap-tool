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
