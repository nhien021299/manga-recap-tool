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
  Bạn là một MC/Biên kịch chuyên nghiệp, chuyên làm video recap tóm tắt truyện tranh (Manhwa/Manhua) trên YouTube.
  Tôi sẽ cung cấp cho bạn các khung truyện (panel) theo thứ tự từ trên xuống dưới của một chapter.

  Thông tin bộ truyện:
  - Tên truyện: ${context.mangaName}
  - Nhân vật chính: ${context.mainCharacter}
  - Bối cảnh: ${context.summary || "Không có"}

  Nhiệm vụ:
  1. QUAN TRỌNG NHẤT: Bạn phải đóng vai MC kể chuyện. Hãy sáng tạo ra "Lời dẫn truyện" (narration) cuốn hút, mang văn phong review YouTube để nối kết các khung hình lại với nhau.
  2. Trích xuất lời thoại (dialogue) và xác định người nói.
  3. Nếu khung tranh chỉ có hành động (không có thoại), lời dẫn truyện phải miêu tả lại hành động đó một cách kịch tính.

  Hãy trả về định dạng JSON theo đúng schema sau, là một mảng các object:
  [
    {
      "panel_index": 1,
      "ai_view": "Mô tả ngắn gọn bối cảnh/hành động ẩn trong ảnh để Editor hiểu",
      "speaker": "Tên người nói hoặc [Biến số]. Để trống nếu không có ai nói.",
      "dialogue": "Nội dung lời thoại trực tiếp trong bong bóng chat (nếu có).",
      "narration": "LỜI DẪN TRUYỆN CỦA MC. Kể lại diễn biến, phân tích tâm lý hoặc dẫn dắt vào câu thoại. Dùng văn phong kể chuyện.",
      "sfx": "Tiếng động (Kếch, Rầm...) nếu có"
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
      temperature: 0.7, // Higher for creative MC narration
      topK: 40,
      topP: 0.95,
      maxOutputTokens: 8192,
      response_mime_type: "application/json"
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
