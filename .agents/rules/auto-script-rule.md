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
Bước 3: Gọi Gemini Flash 3 API (The Magic)
Bạn cài đặt thư viện chính thức của Google cho frontend: npm install @google/generative-ai.

Đây là phần Prompt Engineering cốt lõi để Gemini vừa đóng vai trò OCR, vừa làm biên kịch. Chúng ta sẽ ép nó trả về định dạng JSON để bạn dễ dàng render lên giao diện.

prompt = 
  Bạn là một biên kịch chuyên nghiệp, chuyên tóm tắt truyện tranh (Manhwa/Manhua).
  Tôi sẽ cung cấp cho bạn các khung truyện (panel) theo thứ tự từ trên xuống dưới của một chapter.

  Thông tin bộ truyện:
  - Tên truyện: ${globalContext.mangaName}
  - Nhân vật chính: ${globalContext.mainCharacter}
  - Bối cảnh: ${globalContext.summary || "Không có"}

  Nhiệm vụ:
  1. Đọc tất cả lời thoại và hiệu ứng âm thanh (SFX) trong các bức ảnh.
  2. Phân tích ngữ cảnh để xác định ai đang nói (Dựa vào Tên nhân vật chính đã cung cấp ở trên). Nếu không biết tên, hãy dùng format: [Nhân vật A], [Kẻ thù], [Dân làng].
  3. Viết kịch bản recap tóm tắt lại diễn biến, kết hợp thoại và hành động.

  Hãy trả về định dạng JSON theo đúng schema sau, là một mảng các object:
  [
    {
      "panel_index": 1, // Số thứ tự khung truyện tương ứng
      "scene_description": "Mô tả ngắn gọn bối cảnh/hành động trong ảnh",
      "speaker": "Tên người nói hoặc [Biến số]",
      "dialogue": "Nội dung lời thoại đã được chỉnh sửa cho tự nhiên",
      "sfx": "Tiếng sấm sét (nếu có)"
    }
  ]
  `
Bước 4: Hậu kỳ Script trên Giao diện (Frontend UI)
Sau khi hàm trên chạy xong (thường mất khoảng 5-10 giây cho một lô ảnh dài), bạn sẽ nhận được một mảng JSON sạch đẹp. Giờ thì dùng sức mạnh của Frontend để làm UI:

Render Timeline: Hiển thị mỗi object trong JSON thành một khối (Card) trên màn hình. Bên trái là cái ảnh Panel nhỏ, bên phải là Textbox chứa speaker và dialogue.

Tính năng thay thế biến số (The UI Trick):

Dùng Regex quét toàn bộ data JSON xem có chuỗi nào dạng [...] (ví dụ [Kẻ thù]) không.

Nếu có, render một cái Alert ở góc trên màn hình: "Phát hiện nhân vật vô danh: [Kẻ thù]. Nhập tên thật: [ Ô Input ] [ Nút Replace ]".

Khi bạn gõ "Lão tổ" và bấm Replace, nó sẽ lặp qua mảng JSON và đổi chữ, UI tự động cập nhật ngay lập tức.

Tự do Edit: Người dùng (bạn) có thể click thẳng vào textbox dialogue để sửa lại văn phong cho hợp ý trước khi xuất file âm thanh.