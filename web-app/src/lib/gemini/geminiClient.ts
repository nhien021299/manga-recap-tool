import type { Panel, PanelUnderstanding, ScriptContext, ScriptItem } from '@/types';
import noteScriptTemplateRaw from '../../../note_script.txt?raw';

const BATCH_SIZE = 20;
// const MODEL = 'gemini-3-flash-preview';
const MODEL = 'gemini-2.5-flash';

const MAX_OUTPUT_TOKENS = 65536;
const NOTE_SCRIPT_TEMPLATE = noteScriptTemplateRaw.trim();

type LogCallback = (type: 'request' | 'result' | 'error', message: string, details?: string) => void;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchWithRetry(url: string, options: RequestInit, onLog?: LogCallback, maxRetries = 3): Promise<Response> {
  let attempt = 0;

  while (attempt <= maxRetries) {
    try {
      const response = await fetch(url, options);
      if (response.ok || (response.status !== 503 && response.status !== 429 && response.status !== 500)) {
        return response;
      }

      attempt += 1;
      if (attempt > maxRetries) return response;

      const waitTime = Math.pow(2, attempt) * 1000;
      onLog?.('error', `Lỗi ${response.status}. Thử lại lần ${attempt}/${maxRetries} sau ${waitTime / 1000} giây...`);
      await delay(waitTime);
    } catch (error: any) {
      attempt += 1;
      if (attempt > maxRetries) throw error;

      const waitTime = Math.pow(2, attempt) * 1000;
      onLog?.('error', `Lỗi mạng: ${error.message}. Thử lại lần ${attempt}/${maxRetries} sau ${waitTime / 1000} giây...`);
      await delay(waitTime);
    }
  }

  throw new Error('Maximum retries reached.');
}

type GeminiCallOptions = {
  prompt: string;
  inlineDataParts?: Array<{ inlineData: { mimeType: string; data: string } }>;
};

async function callGemini(apiKey: string, options: GeminiCallOptions, onLog?: LogCallback) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${apiKey}`;
  const body = {
    contents: [
      {
        parts: [
          { text: options.prompt },
          ...(options.inlineDataParts ?? []),
        ],
      },
    ],
    generationConfig: {
      temperature: 0.7,
      topK: 40,
      topP: 0.95,
      maxOutputTokens: MAX_OUTPUT_TOKENS,
      response_mime_type: 'application/json',
    },
  };

  onLog?.(
    'request',
    'Gemini API Call',
    JSON.stringify(
      {
        model: MODEL,
        promptLength: options.prompt.length,
        inlineAssetCount: options.inlineDataParts?.length ?? 0,
        generationConfig: body.generationConfig,
      },
      null,
      2
    )
  );

  const response = await fetchWithRetry(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    onLog
  );

  if (!response.ok) {
    const errorData = await response.json();
    const message = errorData.error?.message || `HTTP ${response.status}`;
    onLog?.('error', `Gemini API error: ${message}`, JSON.stringify(errorData, null, 2));
    throw new Error(message);
  }

  const data = await response.json();
  const textContent = data.candidates?.[0]?.content?.parts?.[0]?.text;
  const finishReason = data.candidates?.[0]?.finishReason;

  if (!textContent) {
    onLog?.('error', 'Gemini trả về nội dung rỗng', JSON.stringify(data, null, 2));
    throw new Error('Empty response from Gemini');
  }

  if (finishReason === 'MAX_TOKENS') {
    onLog?.('error', 'Output bị cắt do vượt token limit', JSON.stringify(data, null, 2));
  }

  return textContent;
}

function panelToInlineData(panel: Panel) {
  const base64Content = panel.base64.split('base64,')[1];
  return {
    inlineData: {
      mimeType: panel.base64.match(/data:(image\/[^;]+);/)?.[1] || 'image/jpeg',
      data: base64Content,
    },
  };
}

function parseJsonArray<T>(text: string, label: string): T[] {
  let cleanText = text.trim();
  if (cleanText.startsWith('```json')) cleanText = cleanText.substring(7);
  if (cleanText.startsWith('```')) cleanText = cleanText.substring(3);
  if (cleanText.endsWith('```')) cleanText = cleanText.slice(0, -3);
  cleanText = cleanText.trim();

  try {
    const parsed = JSON.parse(cleanText);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    try {
      if (!cleanText.endsWith(']')) {
        const lastBrace = cleanText.lastIndexOf('}');
        if (lastBrace !== -1) {
          const fixedText = cleanText.substring(0, lastBrace + 1) + '\n]';
          const parsed = JSON.parse(fixedText);
          if (Array.isArray(parsed)) {
            return parsed;
          }
        }
      }
    } catch {
      // fall through
    }

    throw new Error(`[Parse Error] Không thể parse ${label}.\n\n=== NỘI DUNG THÔ TRẢ VỀ ===\n${cleanText}`);
  }
}

function buildUnderstandingPrompt(context: ScriptContext, panelCount: number, startIndex: number): string {
  return `
Bạn là visual analyst cho manhwa recap. Hãy xem ${panelCount} panel theo thứ tự từ trên xuống dưới và trả về JSON mô tả có cấu trúc cho từng panel.

Thông tin bộ truyện:
- Tên truyện: ${context.mangaName}
- Nhân vật chính: ${context.mainCharacter}
- Bối cảnh: ${context.summary || 'Không có'}

Mục tiêu:
1. Không viết narration review.
2. Chỉ giữ thông tin thật sự cần cho tầng 2 viết lời kể YouTube Recap High-Tension.
3. Mỗi field phải ngắn, gọn, giàu ý, tránh giải thích dài dòng.
4. Nếu có thoại/chữ, chỉ tóm tắt phần cốt lõi chứ không chép lại dài dòng.
5. Không cần debug chi tiết, không cần mô tả dư thừa.

Trả về JSON array theo schema:
[
  {
    "panel_index": ${startIndex},
    "summary": "Tóm tắt rất ngắn, khoảng 8-16 từ.",
    "action": "Hành động chính, rất ngắn.",
    "emotion": "1-3 từ chỉ cảm xúc chính.",
    "dialogue": "Tóm tắt cực ngắn lời thoại/chữ nếu thật sự quan trọng, không có thì để rỗng.",
    "sfx": ["sấm sét", "chấn động"],
    "cliffhanger": "1 mệnh đề ngắn gây tò mò cho panel sau."
  }
]

QUAN TRỌNG:
- Chỉ trả về JSON array, không markdown.
- Đúng ${panelCount} item cho ${panelCount} panels.
- panel_index bắt đầu từ ${startIndex} và tăng dần.
- Không thêm field ngoài schema trên.
`;
}

function buildNarrationPrompt(
  context: ScriptContext,
  items: PanelUnderstanding[],
  startIndex: number,
  previousScriptContext?: string
): string {
  const templateBlock = NOTE_SCRIPT_TEMPLATE
    ? `
Đây là script note nội bộ cần bám theo khi viết:
---
${NOTE_SCRIPT_TEMPLATE}
---
`
    : '';

  const contextBlock = previousScriptContext
    ? `
ĐÂY LÀ PHẦN TIẾP THEO CỦA CHAPTER. Dưới đây là tóm tắt narration phần trước để bạn giữ mạch truyện:
---
${previousScriptContext}
---
Hãy tiếp tục câu chuyện từ đây, giữ nguyên giọng kể, tên nhân vật, và nhịp điệu.
`
    : '';

  const understandingBlock = items
    .map((item, index) => {
      const panelIndex = startIndex + index;
      const compactFields = [
        item.summary ? `Tóm tắt: ${item.summary}` : '',
        item.action ? `Hành động: ${item.action}` : '',
        item.emotion ? `Cảm xúc: ${item.emotion}` : '',
        item.dialogue ? `Thoại/chữ: ${item.dialogue}` : '',
        item.sfx?.length ? `SFX: ${item.sfx.join(', ')}` : '',
        item.cliffhanger ? `Mồi sau: ${item.cliffhanger}` : '',
      ].filter(Boolean);

      return `[Panel ${panelIndex}] ${compactFields.join(' | ')}`;
    })
    .join('\n');

  return `
Bạn là một MC/Biên kịch chuyên làm video recap tóm tắt truyện tranh trên YouTube theo style "YouTube Recap High-Tension".
Bạn KHÔNG cần tự đoán hình ảnh nữa. Bạn phải viết narration dựa trên panel understanding đã được chuẩn hóa sẵn bên dưới.

Thông tin bộ truyện:
- Tên truyện: ${context.mangaName}
- Nhân vật chính: ${context.mainCharacter}
- Bối cảnh: ${context.summary || 'Không có'}
${templateBlock}
${contextBlock}

Panel understanding:
---
${understandingBlock}
---

Nhiệm vụ:
1. Viết voiceover_text liền mạch, nhịp nhanh, cuốn, căng, có lực kéo người nghe sang panel tiếp theo.
2. Dùng style YouTube Recap High-Tension: câu ngắn và vừa, có lực nhấn, có cảm giác đang có biến, sắp lật kèo, nguy hiểm tăng dần.
3. Nếu dialogue xuất hiện trong understanding, hãy hòa vào narration bằng động từ và từ nối. Không tách thành kiểu báo cáo.
4. ai_view phải tóm tắt góc nhìn, bối cảnh, hành động vật lý, chi tiết đang chú ý của từng panel.
5. sfx phải lấy từ understanding, có thể chuẩn hóa nhẹ nhưng không invent vô căn cứ.
6. Chỉ dùng đúng thông tin cần thiết từ understanding để viết, không diễn giải lại toàn bộ dữ liệu đầu vào.
7. Không viết quá dài dòng. Không viết đều đều. Không lặp lại ý trong cùng panel.

Trả về JSON array:
[
  {
    "panel_index": ${startIndex},
    "ai_view": "Mô tả bối cảnh và hành động vật lý của panel.",
    "voiceover_text": "Narration cuốn, liền mạch, nghe đã tai cho 1 người đọc.",
    "sfx": ["sấm sét", "chém kiếm"]
  }
]

QUAN TRỌNG:
- Chỉ trả về JSON array, không markdown.
- Đúng ${items.length} item cho ${items.length} panels.
- panel_index bắt đầu từ ${startIndex} và tăng dần.
`;
}

function buildNarrationContextSummary(items: ScriptItem[], context: ScriptContext): string {
  const narrativeLines = items.map((item) => {
    let line = `[Panel ${item.panel_index}]`;
    if (item.ai_view) line += ` ${item.ai_view}.`;
    if (item.voiceover_text) line += ` Lời kể: "${item.voiceover_text}"`;
    return line;
  });

  return `Truyện "${context.mangaName}", nhân vật chính: ${context.mainCharacter}.\nDiễn biến gần nhất:\n${narrativeLines.join('\n')}`;
}

type PanelUnderstandingApiItem = {
  panel_index: number;
  summary: string;
  action: string;
  emotion: string;
  dialogue: string;
  sfx: string[];
  cliffhanger: string;
};

export const generatePanelUnderstandingsDirect = async (
  apiKey: string,
  panels: Panel[],
  context: ScriptContext,
  onLog?: LogCallback
): Promise<{ items: PanelUnderstanding[]; rawOutput: string }> => {
  if (!apiKey) throw new Error('Vui lòng nhập Gemini API Key trong Settings');

  const totalBatches = Math.ceil(panels.length / BATCH_SIZE);
  const allItems: PanelUnderstanding[] = [];
  const rawOutputs: string[] = [];

  for (let batchIndex = 0; batchIndex < totalBatches; batchIndex += 1) {
    const start = batchIndex * BATCH_SIZE;
    const end = Math.min(start + BATCH_SIZE, panels.length);
    const batchPanels = panels.slice(start, end);
    const startIndex = start + 1;
    const prompt = buildUnderstandingPrompt(context, batchPanels.length, startIndex);

    onLog?.('request', `Stage 1/2 - Panel understanding batch ${batchIndex + 1}/${totalBatches}`, `Panels ${startIndex} -> ${end}`);

    const rawText = await callGemini(
      apiKey,
      {
        prompt,
        inlineDataParts: batchPanels.map(panelToInlineData),
      },
      onLog
    );

    rawOutputs.push(rawText);
    const parsed = parseJsonArray<PanelUnderstandingApiItem>(rawText, 'panel understanding');

    parsed.forEach((item, index) => {
      const panel = batchPanels[index];
      allItems.push({
        panelId: panel.id,
        orderIndex: start + index,
        summary: item.summary || '',
        action: item.action || '',
        emotion: item.emotion || '',
        dialogue: item.dialogue || '',
        sfx: Array.isArray(item.sfx) ? item.sfx : [],
        cliffhanger: item.cliffhanger || '',
      });
    });

    onLog?.('result', `Stage 1/2 complete for batch ${batchIndex + 1}/${totalBatches}`, JSON.stringify(parsed, null, 2));
  }

  return {
    items: allItems,
    rawOutput: rawOutputs.join('\n\n---\n\n'),
  };
};

export const generateNarrationFromUnderstandingsDirect = async (
  apiKey: string,
  understandings: PanelUnderstanding[],
  context: ScriptContext,
  onLog?: LogCallback
): Promise<{ items: ScriptItem[]; rawOutput: string }> => {
  if (!apiKey) throw new Error('Vui lòng nhập Gemini API Key trong Settings');

  const totalBatches = Math.ceil(understandings.length / BATCH_SIZE);
  let previousContext: string | undefined;
  let allResults: ScriptItem[] = [];
  const rawOutputs: string[] = [];

  for (let batchIndex = 0; batchIndex < totalBatches; batchIndex += 1) {
    const start = batchIndex * BATCH_SIZE;
    const end = Math.min(start + BATCH_SIZE, understandings.length);
    const batchItems = understandings.slice(start, end);
    const startIndex = start + 1;
    const prompt = buildNarrationPrompt(context, batchItems, startIndex, previousContext);

    onLog?.('request', `Stage 2/2 - Narration batch ${batchIndex + 1}/${totalBatches}`, `Panels ${startIndex} -> ${end}`);

    const rawText = await callGemini(apiKey, { prompt }, onLog);
    rawOutputs.push(rawText);

    const parsed = parseJsonArray<ScriptItem>(rawText, 'script narration').map((item, index) => ({
      ...item,
      panel_index: startIndex + index,
    }));

    allResults = [...allResults, ...parsed];
    previousContext = buildNarrationContextSummary(parsed, context);

    onLog?.('result', `Stage 2/2 complete for batch ${batchIndex + 1}/${totalBatches}`, JSON.stringify(parsed, null, 2));
  }

  return {
    items: allResults,
    rawOutput: rawOutputs.join('\n\n---\n\n'),
  };
};
