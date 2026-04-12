---
trigger: manual
---

Bước 1: Giao diện thiết lập bối cảnh (Global Context UI)
Trước khi bấm nút "Generate Script", hãy làm một form nhỏ trên UI để bạn mớm thông tin cho AI.

Tên truyện: (Input text - VD: Cầu Ma)

Tên Nhân vật chính: (Input text - VD: Tô Minh)

Bối cảnh tóm tắt (Tùy chọn): (Textarea - VD: Main đang bị truy sát trên vách núi)

Bước 2: Chuẩn bị Dữ liệu (Payload Preparation)
Từ cái Web Worker cắt ảnh của bạn, bạn sẽ thu được một mảng các ảnh panel (đã crop). Bạn cần chuyển đổi các ảnh này sang định dạng Base64 để gửi qua API của Gemini.

JavaScript
// Giả sử bạn có mảng các blob/file ảnh từ bước Crop
async function prepareImagesForGemini(imageFiles) {
  const base64Images = await Promise.all(
    imageFiles.map(async (file) => {
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          // Lấy phần data base64 (bỏ đi prefix data:image/png;base64,)
          const base64Data = reader.result.split(',')[1]; 
          resolve({
            inlineData: {
              data: base64Data,
              mimeType: file.type // ví dụ: "image/jpeg"
            }
          });
        };
        reader.readAsDataURL(file);
      });
    })
  );
  return base64Images;
}

Bước 3: Gọi Gemini API (The Magic)
Sử dụng thuần REST API Client (không cần SDK). Prompt được thiết kế để Gemini đóng vai MC/Biên kịch YouTube, vừa OCR dialogue vừa sáng tác lời dẫn truyện kịch tính.

prompt = `
  Bạn là một MC/Biên kịch chuyên nghiệp, chuyên làm video recap tóm tắt truyện tranh (Manhwa/Manhua) trên YouTube.
  Tôi sẽ cung cấp cho bạn các khung truyện (panel) theo thứ tự từ trên xuống dưới của một chapter.

  Thông tin bộ truyện:
  - Tên truyện: ${globalContext.mangaName}
  - Nhân vật chính: ${globalContext.mainCharacter}
  - Bối cảnh: ${globalContext.summary || "Không có"}

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
  `

Bước 4: Hậu kỳ Script trên Giao diện (Frontend UI)
Sau khi hàm trên chạy xong (thường mất khoảng 5-10 giây cho một lô ảnh dài), bạn sẽ nhận được một mảng JSON sạch đẹp. Giờ thì dùng sức mạnh của Frontend để làm UI:

Render Timeline: Hiển thị mỗi object trong JSON thành một khối (Card) trên màn hình. Bên trái là cái ảnh Panel nhỏ, bên phải gồm:
- Ô Textarea chính: "Lời dẫn truyện MC" (narration) — đây là nội dung MC sẽ đọc khi lồng tiếng.
- Ô Textarea phụ: "Thoại gốc" (dialogue) — lời thoại trực tiếp trích xuất từ bong bóng chat.
- Input: "Người nói" (speaker) — tên nhân vật đang nói.
- Footer: "AI View" (ai_view) — mô tả nội bộ cho Editor hiểu bối cảnh.
- Input nhỏ: "SFX" — hiệu ứng âm thanh.

Cách gộp chung (Khuyên dùng cho MC đọc mượt):
Khi xuất audio (TTS), nối narration và dialogue:
```
const displayText = item.dialogue 
  ? `${item.narration}\n\n"${item.dialogue}"` 
  : item.narration;
```

Tính năng thay thế biến số (The UI Trick):

Dùng Regex quét toàn bộ data JSON (speaker, dialogue, narration) xem có chuỗi nào dạng [...] (ví dụ [Kẻ thù]) không.

Nếu có, render một cái Alert ở góc trên màn hình: "Phát hiện nhân vật vô danh: [Kẻ thù]. Nhập tên thật: [ Ô Input ] [ Nút Replace ]".

Khi bạn gõ "Lão tổ" và bấm Replace, nó sẽ lặp qua mảng JSON và đổi chữ, UI tự động cập nhật ngay lập tức.

Tự do Edit: Người dùng (bạn) có thể click thẳng vào textbox narration/dialogue để sửa lại văn phong cho hợp ý trước khi xuất file âm thanh.