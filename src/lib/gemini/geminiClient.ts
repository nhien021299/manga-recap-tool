import type { Panel, ScriptContext, ScriptItem } from '@/types';

/**
 * Gemini Script Generator Client
 * Uses advanced Prompt Engineering for OCR + Screenwriting
 */
export const generateScriptDirect = async (
  apiKey: string,
  panels: Panel[],
  context: ScriptContext
): Promise<ScriptItem[]> => {
  if (!apiKey) throw new Error("Vui lòng nhập Gemini API Key trong Settings");

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=${apiKey}`;

  const prompt = `
  Bạn là một biên kịch chuyên nghiệp, chuyên tóm tắt truyện tranh (Manhwa/Manhua).
  Tôi sẽ cung cấp cho bạn các khung truyện (panel) theo thứ tự từ trên xuống dưới của một chapter.

  Thông tin bộ truyện:
  - Tên truyện: ${context.mangaName}
  - Nhân vật chính: ${context.mainCharacter}
  - Bối cảnh: ${context.summary || "Không có"}

  Nhiệm vụ:
  1. Đọc tất cả lời thoại và hiệu ứng âm thanh (SFX) trong các bức ảnh.
  2. Phân tích ngữ cảnh để xác định ai đang nói (Dựa vào Tên nhân vật chính đã cung cấp ở trên). Nếu không biết tên, hãy dùng format: [Nhân vật A], [Kẻ thù], [Dân làng].
  3. Viết kịch bản recap tóm tắt lại diễn biến, kết hợp thoại và hành động.

  Hãy trả về định dạng JSON theo đúng schema sau, là một mảng các object:
  [
    {
      "panel_index": 1, 
      "scene_description": "Mô tả ngắn gọn bối cảnh/hành động trong ảnh",
      "speaker": "Tên người nói hoặc [Biến số]",
      "dialogue": "Nội dung lời thoại đã được chỉnh sửa cho tự nhiên",
      "sfx": "Tiếng sấm sét (nếu có)"
    }
  ]
  
  QUAN TRỌNG: Chỉ trả về mảng JSON, không bọc trong markdown. Thứ tự item trong mảng phải khớp với thứ tự panel gửi lên.
  `;

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
      temperature: 0.4, // Lower for more accurate OCR
      topK: 40,
      topP: 0.95,
      maxOutputTokens: 8192,
      response_mime_type: "application/json" // Force JSON output mode if supported
    }
  };

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error?.message || "Lỗi khi gọi Gemini API");
  }

  const data = await response.json();
  const textContent = data.candidates?.[0]?.content?.parts?.[0]?.text;

  if (!textContent) throw new Error("Empty response from Gemini");

  return parseGeminiResponse(textContent);
};

function parseGeminiResponse(text: string): ScriptItem[] {
  try {
    let cleanText = text.trim();
    // Clean up markdown if any
    if (cleanText.startsWith('```json')) cleanText = cleanText.substring(7);
    if (cleanText.startsWith('```')) cleanText = cleanText.substring(3);
    if (cleanText.endsWith('```')) cleanText = cleanText.slice(0, -3);

    const parsed = JSON.parse(cleanText.trim());
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error("Raw Gemini output was:", text);
    throw new Error("Không thể parse kịch bản AI. Thử lại hoặc rút ngắn số lượng panel.");
  }
}
