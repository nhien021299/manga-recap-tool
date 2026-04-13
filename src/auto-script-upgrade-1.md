Dưới đây là bản thiết kế (Blueprint) chi tiết để bạn refactor lại geminiClient và UI Logic, đảm bảo hệ thống tự động hóa hoàn toàn việc gộp thoại và trigger SFX.

1. Cập nhật Data Contract (Interface/Types)

Vì thoại và dẫn truyện đã gộp chung, bạn không cần giữ các trường speaker, dialogue, narration rời rạc nữa. Khối lượng dữ liệu trả về sẽ gọn hơn.

Sửa lại interface ScriptItem trong file types.ts của bạn:

TypeScript
export interface ScriptItem {
panel_index: number;
ai_view: string; // Vẫn giữ để làm Prompt cho model gen ảnh/video
voiceover_text: string; // Đã gộp toàn bộ Lời dẫn + Thoại + Từ nối
sfx: string[]; // Chuyển từ string sang Array<string> để dễ query file mp3
} 2. Nâng cấp Prompt Layer (geminiClient.ts)

Ta sẽ sửa đổi hàm buildPrompt để "ép" LLM làm công việc của một biên tập viên: tự động chèn từ nối và phân tích âm thanh môi trường.

TypeScript
function buildPrompt(
context: ScriptContext,
panelCount: number,
startIndex: number,
previousScriptContext?: string
): string {
const contextBlock = previousScriptContext
? `
⚠️ Dưới đây là tóm tắt kịch bản phần trước để bạn nắm mạch truyện:

---

${previousScriptContext}

---

Hãy TIẾP TỤC câu chuyện, giữ nguyên giọng kể và mạch cảm xúc.
Panel tiếp theo bắt đầu từ index ${startIndex}.
`
: '';

return `
Bạn là một MC/Biên kịch chuyên nghiệp, chuyên làm video recap tóm tắt truyện tranh trên YouTube.
Tôi sẽ cung cấp ${panelCount} khung truyện (panel) theo thứ tự từ trên xuống.

Thông tin truyện:

- Tên truyện: ${context.mangaName}
- Nhân vật chính: ${context.mainCharacter}
- Bối cảnh: ${context.summary || "Không có"}
  ${contextBlock}

Nhiệm vụ:

1. Viết "Lời dẫn truyện" (voiceover_text) liền mạch để một MC đọc từ đầu đến cuối.
2. NẾU CÓ THOẠI: BẮT BUỘC phải tự động chèn các động từ/từ nối để gộp thoại vào lời dẫn.
   (Ví dụ sai: "Kẻ thù: 'Chết đi!'" -> Ví dụ đúng: "Kẻ thù gầm lên dữ dội, vung kiếm hét lớn 'Chết đi!'").
3. Phân tích hình ảnh để trích xuất các hiệu ứng âm thanh (SFX) quan trọng như: tiếng sấm, chém kiếm, đổ vỡ, bước chân...

Trả về định dạng JSON, là một mảng object:
[
{
"panel_index": ${startIndex},
"ai_view": "Mô tả bối cảnh/hành động vật lý ẩn trong ảnh (ví dụ: góc máy hắt từ dưới lên, chớp lóe sáng...).",
"voiceover_text": "Kịch bản dẫn truyện ĐÃ BAO GỒM LỜI THOẠI và từ nối. Viết trôi chảy cho 1 người đọc.",
"sfx": ["sấm sét", "chém kiếm"] // Mảng các từ khóa âm thanh. Trống [] nếu tĩnh lặng.
}
]

Chỉ trả về JSON thuần, không bọc markdown. Số lượng item phải đúng bằng ${panelCount}.
`;
}
Lưu ý ở hàm buildContextSummary của bạn cũng cần update lại phần map text theo key mới voiceover_text để các batch sau nhận đúng context.

3. Nâng cấp UI Logic (State & Presentation)

Khi cấu trúc dữ liệu đã thay đổi, giao diện thao tác của Editor cần tinh gọn lại theo kiến trúc luồng dữ liệu mới:

Vùng Nhập Liệu (Voiceover): Thay vì 3 ô (Lời dẫn, Thoại, Người nói), giờ chỉ còn 1 Textarea lớn duy nhất mang tên "Kịch Bản Đọc". Việc này giúp user dễ dàng rà soát lại flow của người kể chuyện.

Vùng SFX (Âm thanh): \* Hiển thị trường sfx dưới dạng các Tag/Chip (ví dụ: [🌩️ Sấm sét], [⚔️ Tiếng kiếm]).

UI nên cho phép user click vào Tag để đổi file âm thanh khác hoặc thêm/xóa tag thủ công.

4. Agent Pipeline: Xử lý Audio & Mapping (Bản lề quan trọng)

Để Agent tự động hóa được luồng âm thanh, bạn cần xây dựng một "SFX Dictionary" (Từ điển âm thanh) ở backend hoặc load sẵn ở frontend.

TTS Generation (Voice MC): Đẩy thẳng trường voiceover_text vào API Text-to-Speech (như ElevenLabs, Azure, hoặc Google TTS). Cả đoạn "Hắn thét lên má ơi" sẽ được đọc mượt mà bởi một giọng.

SFX Mapping & Mixing:

Xây dựng một mapping đơn giản:

JSON
{
"sấm sét": "thunder_01.mp3",
"chém kiếm": "sword_slash_fast.mp3",
"bước chân": "footsteps_dirt.mp3"
}
Khi Agent nhận được sfx: ["sấm sét"], nó sẽ tự động pick file thunder_01.mp3 và overlay (đặt chồng) lên timeline video tại đúng thời điểm xuất hiện của Panel đó.

Mẹo: Nên để volume của luồng TTS ở mức 100%, luồng SFX ở mức 40-60% để âm thanh môi trường không lấn át giọng đọc của MC. Giảm âm lượng SFX (audio ducking) là technique bắt buộc để video nghe chuyên nghiệp.
