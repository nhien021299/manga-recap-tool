import type { Panel, ScriptContext, ScriptItem } from '@/types';

/**
 * Gemini Script Generator Client
 * Uses Chunked Generation with Context Passing for large chapters.
 * Panels are split into batches. Each batch receives the previous batch's
 * script as narrative context, ensuring story flow continuity.
 */

const BATCH_SIZE = 20; // panels per API call
const MODEL = 'gemini-3-flash-preview';
const MAX_OUTPUT_TOKENS = 65536;

type LogCallback = (type: 'request' | 'result' | 'error', message: string, details?: string) => void;

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function fetchWithRetry(url: string, options: RequestInit, onLog?: LogCallback, maxRetries = 3): Promise<Response> {
  let attempt = 0;
  
  while (attempt <= maxRetries) {
    try {
      const response = await fetch(url, options);
      
      // If success or a non-retriable error (e.g., 400 Bad Request), return immediately
      if (response.ok || (response.status !== 503 && response.status !== 429 && response.status !== 500)) {
        return response;
      }
      
      attempt++;
      if (attempt > maxRetries) return response; // Return the failed response to be handled by caller
      
      const waitTime = Math.pow(2, attempt) * 1000; // 2s, 4s, 8s...
      onLog?.('error', `Lỗi ${response.status} (Server quá tải). Thử lại lần ${attempt}/${maxRetries} sau ${waitTime/1000} giây...`);
      await delay(waitTime);
      
    } catch (err: any) {
      // Network errors (e.g., DNS, offline)
      attempt++;
      if (attempt > maxRetries) throw err;
      
      const waitTime = Math.pow(2, attempt) * 1000;
      onLog?.('error', `Lỗi mạng: ${err.message}. Thử lại lần ${attempt}/${maxRetries} sau ${waitTime/1000} giây...`);
      await delay(waitTime);
    }
  }
  
  throw new Error("Maximum retries reached.");
}

// ─── PUBLIC: Main entry point ────────────────────────────────────────────────

export const generateScriptDirect = async (
  apiKey: string,
  panels: Panel[],
  context: ScriptContext,
  onLog?: LogCallback
): Promise<ScriptItem[]> => {
  if (!apiKey) throw new Error("Vui lòng nhập Gemini API Key trong Settings");

  // If panel count fits in a single call, do it directly
  if (panels.length <= BATCH_SIZE) {
    onLog?.('request', `Chế độ: Single-shot (${panels.length} panels)`, `Toàn bộ ${panels.length} panel sẽ được gửi trong 1 lần gọi API.`);
    return await callGemini(apiKey, panels, context, 1, undefined, onLog);
  }

  // ── Chunked mode ──
  const totalBatches = Math.ceil(panels.length / BATCH_SIZE);
  onLog?.('request', `Chế độ: Chunked Generation (${panels.length} panels → ${totalBatches} batches)`, 
    `Mỗi batch gồm ~${BATCH_SIZE} panels.\nBatch sau sẽ nhận kịch bản batch trước làm context để giữ mạch truyện.`);

  let allResults: ScriptItem[] = [];
  let previousContext: string | undefined = undefined;

  for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
    const start = batchIndex * BATCH_SIZE;
    const end = Math.min(start + BATCH_SIZE, panels.length);
    const batchPanels = panels.slice(start, end);
    const batchNumber = batchIndex + 1;

    onLog?.('request', `── Batch ${batchNumber}/${totalBatches} ── Panels ${start + 1}→${end}`, 
      previousContext 
        ? `Context từ batch trước: ${previousContext.substring(0, 500)}...` 
        : 'Batch đầu tiên, chưa có context trước đó.');

    const batchResults = await callGemini(
      apiKey, batchPanels, context, start + 1, previousContext, onLog
    );

    // Re-index panel_index to be global (not batch-local)
    const reindexed = batchResults.map((item, i) => ({
      ...item,
      panel_index: start + 1 + i
    }));

    allResults = [...allResults, ...reindexed];

    onLog?.('result', `Batch ${batchNumber}/${totalBatches} hoàn thành: ${batchResults.length} scenes`, 
      JSON.stringify(reindexed, null, 2));

    // Build context summary for the NEXT batch from what we just got
    previousContext = buildContextSummary(reindexed, context);
  }

  onLog?.('result', `✅ Hoàn tất tất cả ${totalBatches} batches — Tổng cộng ${allResults.length} scenes.`);
  return allResults;
};

// ─── PRIVATE: Single API call ────────────────────────────────────────────────

async function callGemini(
  apiKey: string,
  panels: Panel[],
  context: ScriptContext,
  startIndex: number,
  previousScriptContext: string | undefined,
  onLog?: LogCallback
): Promise<ScriptItem[]> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${apiKey}`;

  const prompt = buildPrompt(context, panels.length, startIndex, previousScriptContext);

  const inlineDataParts = panels.map((panel) => {
    const base64Content = panel.base64.split('base64,')[1];
    return {
      inlineData: {
        mimeType: panel.base64.match(/data:(image\/[^;]+);/)?.[1] || "image/jpeg",
        data: base64Content
      }
    };
  });

  const body = {
    contents: [
      {
        parts: [
          { text: prompt },
          ...inlineDataParts
        ]
      }
    ],
    generationConfig: {
      temperature: 0.7,
      topK: 40,
      topP: 0.95,
      maxOutputTokens: MAX_OUTPUT_TOKENS,
      response_mime_type: "application/json"
    }
  };

  onLog?.('request', `API Call — ${panels.length} panels (index ${startIndex}→${startIndex + panels.length - 1})`, 
    JSON.stringify({
      model: MODEL,
      generationConfig: body.generationConfig,
      promptLength: prompt.length,
      panelCount: panels.length,
      hasContext: !!previousScriptContext
    }, null, 2));

  const response = await fetchWithRetry(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }, onLog);

  if (!response.ok) {
    const errorData = await response.json();
    const errMsg = errorData.error?.message || `HTTP ${response.status}`;
    onLog?.('error', `API trả về lỗi: ${errMsg}`, JSON.stringify(errorData, null, 2));
    throw new Error(errMsg);
  }

  const data = await response.json();
  const textContent = data.candidates?.[0]?.content?.parts?.[0]?.text;
  const finishReason = data.candidates?.[0]?.finishReason;

  if (!textContent) {
    onLog?.('error', 'API trả về response rỗng', JSON.stringify(data, null, 2));
    throw new Error("Empty response from Gemini");
  }

  if (finishReason === 'MAX_TOKENS') {
    onLog?.('error', '⚠️ Output bị cắt cụt vì vượt Max Tokens!', `finishReason: ${finishReason}\nSẽ cố parse phần đã nhận được...`);
  }

  return parseGeminiResponse(textContent);
}

// ─── PRIVATE: Build prompt ───────────────────────────────────────────────────

function buildPrompt(
  context: ScriptContext,
  panelCount: number,
  startIndex: number,
  previousScriptContext?: string
): string {
  const contextBlock = previousScriptContext 
    ? `
  ⚠️ ĐÂY LÀ PHẦN TIẾP THEO CỦA CHAPTER. Dưới đây là tóm tắt kịch bản phần trước để bạn nắm mạch truyện:
  ---
  ${previousScriptContext}
  ---
  Hãy TIẾP TỤC câu chuyện từ đây, giữ nguyên giọng kể, phong cách MC, và tên nhân vật nhất quán.
  Panel tiếp theo bắt đầu từ index ${startIndex}.
  ` 
    : '';

  return `
  Bạn là một MC/Biên kịch chuyên nghiệp, chuyên làm video recap tóm tắt truyện tranh (Manhwa/Manhua) trên YouTube.
  Tôi sẽ cung cấp cho bạn ${panelCount} khung truyện (panel) theo thứ tự từ trên xuống dưới của một chapter.

  Thông tin bộ truyện:
  - Tên truyện: ${context.mangaName}
  - Nhân vật chính: ${context.mainCharacter}
  - Bối cảnh: ${context.summary || "Không có"}
  ${contextBlock}
  
  Nhiệm vụ:
  1. QUAN TRỌNG NHẤT: Bạn phải đóng vai MC kể chuyện. Hãy viết "Lời dẫn truyện" (voiceover_text) liền mạch để một MC đọc từ đầu đến cuối, dùng văn phong review YouTube để nối kết các khung hình.
  2. NẾU CÓ THOẠI: BẮT BUỘC phải tự động chèn các động từ/từ nối để gộp thoại vào lời dẫn.
     (Ví dụ sai: "Kẻ thù: 'Chết đi!'" -> Ví dụ đúng: "Kẻ thù gầm lên dữ dội, vung kiếm hét lớn 'Chết đi!'").
  3. Phân tích hình ảnh để trích xuất các hiệu ứng âm thanh (SFX) quan trọng như: tiếng sấm, chém kiếm, đổ vỡ, bước chân, tiếng gió...

  Hãy trả về định dạng JSON theo đúng schema sau, là một mảng các object:
  [
    {
      "panel_index": ${startIndex},
      "ai_view": "Mô tả bối cảnh/hành động vật lý ẩn trong ảnh (ví dụ: góc máy hắt từ dưới lên, chớp lóe sáng...).",
      "voiceover_text": "Kịch bản dẫn truyện ĐÃ BAO GỒM LỜI THOẠI và từ nối. Viết trôi chảy cho 1 người đọc.",
      "sfx": ["sấm sét", "chém kiếm"] // Mảng các từ khóa âm thanh. Trống [] nếu tĩnh lặng.
    }
  ]

  QUAN TRỌNG: 
  - Chỉ trả về mảng JSON, không bọc trong markdown.
  - Thứ tự item trong mảng phải khớp với thứ tự panel gửi lên.
  - panel_index bắt đầu từ ${startIndex} và tăng dần.
  - Đảm bảo trả về ĐÚNG ${panelCount} items cho ${panelCount} panels.
  `;
}

// ─── PRIVATE: Build context summary for next batch ───────────────────────────

function buildContextSummary(items: ScriptItem[], context: ScriptContext): string {
  // Create a condensed narrative summary the next batch can use
  const narrativeLines = items.map(item => {
    let line = `[Panel ${item.panel_index}]`;
    if (item.ai_view) line += ` ${item.ai_view}.`;
    if (item.voiceover_text) line += ` Lời kể: "${item.voiceover_text}"`;
    return line;
  });

  return `Truyện "${context.mangaName}", nhân vật chính: ${context.mainCharacter}.\nDiễn biến gần nhất:\n${narrativeLines.join('\n')}`;
}

// ─── PRIVATE: Parse response ─────────────────────────────────────────────────

function parseGeminiResponse(text: string): ScriptItem[] {
  let cleanText = text.trim();
  // Clean up markdown if any
  if (cleanText.startsWith('```json')) cleanText = cleanText.substring(7);
  if (cleanText.startsWith('```')) cleanText = cleanText.substring(3);
  if (cleanText.endsWith('```')) cleanText = cleanText.slice(0, -3);
  cleanText = cleanText.trim();

  try {
    const parsed = JSON.parse(cleanText);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    // Attempt auto-fix for truncated JSON arrays
    try {
      if (!cleanText.endsWith(']')) {
        const lastBrace = cleanText.lastIndexOf('}');
        if (lastBrace !== -1) {
          const fixedText = cleanText.substring(0, lastBrace + 1) + '\n]';
          const parsed = JSON.parse(fixedText);
          if (Array.isArray(parsed)) {
            console.warn(`[Auto-Fix] Recovered ${parsed.length} items from truncated JSON.`);
            return parsed;
          }
        }
      }
    } catch (e) {
      // Fall through to main error
    }
    throw new Error(`[Parse Error] Không thể parse kịch bản AI do dữ liệu bị cắt cụt (vượt quá Token Limit) hoặc sai format.\n\n=== NỘI DUNG THÔ TRẢ VỀ ===\n${cleanText}`);
  }
}
