# Báo cáo Tiến trình Dự án: Manhwa Recap Tool

**Ngày cập nhật**: 13/04/2026
**Mục tiêu dự án**: Xây dựng một công cụ tự động hóa quá trình làm video recap/review truyện tranh (Webtoon/Manhwa) từ khâu tách hình ảnh, tạo kịch bản bằng AI, cho đến thu âm TTS và xuất video. Sử dụng hoàn toàn trên Frontend/Trình duyệt.

---

## 🚀 Tóm tắt Trạng thái Các Milestone

| Milestone | Tính năng | Trạng thái |
|---|---|---|
| **Milestone 1** | Upload & Quản lý UI/State cơ bản | 🟢 Hoàn thành |
| **Milestone 2** | Tách Panel Hình Ảnh Tự Động | 🟢 Hoàn thành |
| **Milestone 3** | Nhận diện & Phân cụm Nhân vật (Face Detection) | ❌ Đã loại bỏ |
| **Milestone 4** | Tạo Kịch Bản Tự Động bằng AI (Gemini) | 🟢 Hoàn thành |
| **Milestone 5** | Lồng tiếng (TTS) | ⏳ Sắp tới |
| **Milestone 6** | Xuất Video (FFmpeg Render) | ⏳ Sắp tới |

---

## 📝 Chi tiết Từng Milestone

### 🟢 Milestone 1: Nền tảng & Upload
- **Mục tiêu**: Xây dựng kiến trúc dự án và cho phép người dùng tải lên hình ảnh truyện tranh dài.
- **Chi tiết**:
  - Khởi tạo dự án bằng Vite + React + TypeScript + TailwindCSS.
  - Sử dụng hệ thống component của `shadcn/ui` mang phong cách "Dark Studio" hiện đại.
  - Sử dụng `Zustand` làm State Management chung cho toàn bộ App (`useRecapStore.ts`), cho phép lưu trữ trạng thái tại Local Storage.
  - Xây dựng Side Navigation Bar linh hoạt, chia làm các luồng rõ ràng (`StepUpload.tsx`).

### 🟢 Milestone 2: Tách Panel (Trích xuất khung truyện)
- **Mục tiêu**: Tự động nhận diện và cắt dải ảnh dọc dài (Webtoon) thành các panel ảnh rời rạc.
- **Chi tiết**:
  - Đã tái cấu trúc toàn bộ sang cơ chế **Virtual Strip** (dải ảnh ảo), tối ưu hiệu năng không làm sập trình duyệt khi người dùng chèn 50+ ảnh dài.
  - Sử dụng Web Worker để chạy thuật toán quét pixel (`EXTRACT_PANELS_ROW_SCAN`) tìm bám sát vào ranh giới từng Panel thực tế (bỏ qua khoảng trắng/padding an toàn).
  - Áp dụng UI kéo thả `SceneOverlay` với `@tanstack/react-virtual` để người dùng dễ dàng tune (tinh chỉnh) độ cao, tạo ra khung ảnh chính xác trước khi xuất.
  - Quản lý metadata (id, thumbnail, base64) để sẵn sàng gửi cho AI ở bước trích xuất kịch bản.
- **Lưu ý Hiện tại (Known Issues)**:
  - Hiện vẫn còn một số lỗi ở bước Cắt Panel (đang fix và tuỳ chỉnh lại UI theo phản hồi của user).

### ❌ Milestone 3: AI Nhận diện Khuôn mặt (Đã loại bỏ)
- **Mục tiêu cũ**: Dùng AI/TensorFlow.js (`@vladmandic/face-api`) để tách lập các khuôn mặt và gom nhóm.
- **Tình trạng**: **Đã hủy bỏ & Dọn dẹp hoàn toàn**.
- **Lý do**:
  - Thư viện quá nặng nề (~12MB file models nạp lên trình duyệt), làm chậm tốc độ mở App.
  - Lỗi bất đồng bộ với Web Worker trên các môi trường.
  - Không cần thiết cho quy trình Recap YouTube hiện đại (Thay vào đó, giao việc hiểu và kết nối câu chuyện cho LLM ở Milestone 4 sẽ tốt và tối ưu hơn).

### 🟢 Milestone 4: Tự động hóa Kịch Bản bằng Gemini AI
- **Mục tiêu**: Thay thế toàn bộ quá trình viết script review thủ công bằng sức mạnh của LLM.
- **Chi tiết**:
  - Nâng cấp UI toàn diện ở mục Step Script (`Auto-Script Upgrade`), hiển thị dạng Message/Bubble tối ưu cho editor rà soát kịch bản.
  - Kết hợp Prompt Engineering để tách giọng (Voiceover text) và sfx (tạo kho json `/public/sfx-dictionary.json` cập nhật tự động khi LLM tạo sfx mới).
  - Tích hợp Exponential Backoff Retry Handling để né lỗi `503 High Demand` của Gemini AI.
  - Lưu và cache State local storage cho phép tiếp tục chỉnh sửa Script/Extract mà không cần làm lại từ đầu trừ khi đổi bộ ảnh Upload.

### ⏳ Milestone 5: Lồng tiếng Tự Động (Voice TTS) - *Sắp tới*
- **Mục tiêu**: Kết nối nội dung Kịch bản ở Milestone 4 vào API chuyển văn bản thành giọng nói (TTS) như ElevenLabs hoặc Google TTS.
- **Dự kiến thực hiện**:
  - Gộp chung văn bản `Narration` và `Dialogue` (hoặc cấu hình tùy ý) gửi tới TTS.
  - Cho phép pre-listen (nghe thử) ở từng thẻ Panel trên giao diện `StepVoice.tsx`.
  - Kết xuất audio cục bộ (Audio Blob) và lưu vào `TimelineItem`.

### ⏳ Milestone 6: Render & Xuất Video (FFmpeg) - *Sắp tới*
- **Mục tiêu**: Đóng gói hình ảnh của Milestone 2 và Âm thanh của Milestone 5 thành 1 file MP4 thành phẩm.
- **Dự kiến thực hiện**:
  - Sử dụng `@ffmpeg/ffmpeg` biên dịch WebAssembly (chạy trực tiếp trong trình duyệt) để render.
  - Timing: Hình ảnh hiển thị theo độ dài của Audio TTS tương ứng.
  - Chèn thêm chuyển cảnh (Crossfade/Pan-zoom) cơ bản (nếu có thể triển khai trên môi trường WASM) để video có cảm giác "sống động".
  - Nút Tải xuống file MP4 thành phẩm.

---

## 📌 Các bước thực hiện tiếp theo cho Dev
1. Thiết kế và build giao diện chi tiết cho luồng **Milestone 5 (Voice)** tại `src/components/steps/StepVoice.tsx`.
2. Connect thư viện TTS (như ElevenLabs SDK REST) vào.
3. Liên kết độ dài Audio của mỗi Panel với tổng Timeline chung.
