Kiến trúc chia nhỏ từng panel như trong Worker hiện tại của bạn rất tốt để trích xuất dữ liệu thô, nhưng đúng là nó sẽ "giết chết" các khung hình toàn cảnh kéo dài. Để chuyển sang luồng "Stitch (Nối) -> Auto-Suggest (Gợi ý) -> Custom Crop (Tinh chỉnh)", chúng ta cần tái cấu trúc lại pipeline này.

Dưới đây là bản thiết kế chi tiết để bạn refactor lại luồng React TS và Web Worker.

Phase 1: Tiền xử lý - Ghép dải ảnh gốc (Vertical Stitching)

Thay vì ném từng ảnh rời rạc vào Worker, bước đầu tiên ở Main Thread (React) là phải tạo ra một "Master Strip" (Dải ảnh gốc).

Xử lý kích thước: Đọc toàn bộ file ảnh người dùng tải lên, tính toán tỷ lệ để quy về cùng một chiều rộng (width) chuẩn (ví dụ: 1080px hoặc 1920px).

Vẽ lên OffscreenCanvas: Cộng dồn chiều cao (height) của tất cả các ảnh. Tạo một OffscreenCanvas (để không block UI) và dùng ctx.drawImage vẽ nối đuôi nhau theo trục Y.

Xuất Master Blob: Chuyển Master Canvas này thành một Image Bitmap hoặc Blob để truyền xuống cho Worker và dùng làm nền cho UI hiển thị.

Phase 2: Nâng cấp Web Worker (Auto-Suggest Anchors)

Worker hiện tại của bạn (EXTRACT_PANELS_ROW_SCAN) đang cố gắng tìm bounding box (x, y, width, height) ôm sát nhất vào nội dung. Chúng ta sẽ sửa nó thành "Auto-Suggest Scenes" dựa trên Viewport (tỷ lệ khung hình video).

Đầu vào mới: Ngoài imageData, truyền thêm viewportRatio (ví dụ: 9/16 cho Short) và viewportHeight (được tính toán từ width của Master Image).

Giữ lại logic Row Scan: Thuật toán đếm pixel trắng của bạn để tìm khoảng trống (minGutterHeight) vẫn rất chuẩn xác. Hãy giữ lại để tìm các điểm ngắt Y an toàn (Y_safe).

Logic tạo Scene (Mới): Thay vì cắt theo contentStart và contentEnd, thuật toán sẽ:

Bắt đầu từ y = 0.

Tạo một khung ảo có chiều cao bằng viewportHeight.

Kiểm tra mép dưới của khung ảo này có đang "chém" ngang qua chữ hay nội dung không (dựa vào mảng Y_safe đã scan ở trên).

Nếu mép dưới nằm trong vùng nội dung, đẩy tọa độ Y xuống cho đến khi gặp điểm Y_safe gần nhất.

Ghi nhận tọa độ { y: currentY, height: targetHeight } vào danh sách suggestedScenes.

Tiếp tục vòng lặp cho đến hết chiều cao ảnh.

Phase 3: Xây dựng ViewFinder UI (React State & Component)

Đây là nơi trải nghiệm người dùng quyết định sự thành bại của tool.

Kiến trúc DOM:

Lớp dưới cùng (Base): Thẻ <img> hoặc <canvas> hiển thị Master Strip. Bọc nó trong một container có overflow-y: scroll.

Lớp tương tác (ViewFinder): Một <div> lơ lửng nằm đè lên trên (position absolute). Nó có viền nổi bật, ở giữa trong suốt, bên ngoài viền có lớp phủ mờ (dim) để làm nổi bật phần đang chọn. Tỷ lệ của nó bị khóa cứng (ví dụ 16:9).

State Management:

masterImageRef: Tham chiếu đến dải ảnh gốc.

scenes: Mảng chứa tọa độ [ { id, y, height, isAuto: true/false } ]. Khởi tạo mảng này bằng kết quả trả về từ Worker.

activeSceneId: Cảnh đang được focus.

Tương tác kéo thả (Drag & Custom):

Render các scenes thành các ô hình chữ nhật trên Minimap hoặc ngay trên dải ảnh.

Khi người dùng nắm kéo khối ViewFinder, cập nhật state y của activeSceneId. Chỉ cần thay đổi y, chiều cao (height) đã được cố định theo tỷ lệ video.

Phase 4: Xuất file & Truyền xuống Agent (Final Render)

Khi người dùng đã hài lòng với chuỗi các cảnh, Main Thread không cần phải cắt ra từng file ảnh vật lý nữa.

Dữ liệu đầu ra: Chỉ cần một mảng JSON nhẹ chứa tọa độ: [ { scene: 1, y_offset: 0 }, { scene: 2, y_offset: 1920 } ...].

Render Video: Khi Agent (hoặc ffmpeg) tiến hành dựng video, nó chỉ cần load một file Master Strip duy nhất và dùng các tọa độ y_offset này để animate việc dịch chuyển camera, hoặc crop trực tiếp trong quá trình render frame.

Trình duyệt có giới hạn cứng về kích thước Canvas (ví dụ: Chrome thường giới hạn chiều cao tối đa ở mức 32,767px, trong khi Safari/iOS còn khắt khe hơn, giới hạn tổng diện tích khoảng 16 Megapixels). Một chapter truyện tranh 50 ảnh ghép lại có thể dễ dàng chạm mốc 50,000px chiều cao và gây crash tab ngay lập tức (lỗi Out of Memory).

Để giải quyết triệt để vấn đề này, chúng ta phải từ bỏ tư duy "ghép tất cả pixel lại thành một bức ảnh khổng lồ". Thay vào đó, bạn cần áp dụng kiến trúc Tile-based Rendering (Render theo lưới) kết hợp Virtual Scrolling (Cuộn ảo).

Dưới đây là kế hoạch kiến trúc chi tiết để xử lý hàng vạn pixel mà không tốn một giọt RAM thừa nào.

Kế Hoạch Nâng Cấp: Kiến trúc "Cuộn Ảo" (Virtualization)

Cốt lõi của phương pháp này là: Chỉ vẽ (render) những gì người dùng đang nhìn thấy trên màn hình, cộng thêm một chút vùng đệm (buffer) phía trên và dưới.

Bước 1: Xây dựng Virtual Strip (Dải ảnh ảo - Quản lý bằng Toán học)

Thay vì dùng OffscreenCanvas để nối ảnh thật, bạn chỉ cần tạo ra một mảng dữ liệu (Metadata) để định vị tọa độ của từng ảnh trong một không gian ảo.

Quét Meta: Khi user tải lên 50 ảnh, vòng lặp nhanh qua tất cả file (dùng Image object hoặc đọc header) để lấy width/height gốc.

Chuẩn hóa Width: Giả sử width chuẩn là 1080px. Tính lại tỷ lệ scale cho height của từng ảnh.

Tính tọa độ Global (Y_offset):

TypeScript
// Ví dụ cấu trúc dữ liệu mảng Virtual Strip
const virtualStrip = [
{ id: 'img_1', file: File, height: 1200, globalY: 0 },
{ id: 'img_2', file: File, height: 1500, globalY: 1200 },
{ id: 'img_3', file: File, height: 800, globalY: 2700 }, // Y_offset cộng dồn
// ...
];
const totalVirtualHeight = 3500; // Tổng chiều cao
Bước 2: Nâng cấp Web Worker (Quét theo Chunk/Khối)

Web worker của bạn không nên nhận một imageData khổng lồ nữa.

Gửi từng phần tử của virtualStrip xuống Worker một cách tuần tự (hoặc song song nếu nhiều Worker).

Worker quét Row Scan trên từng ảnh rời rạc và tìm ra các điểm ngắt (Y_safe) cục bộ (local Y).

Khi Worker trả kết quả về, Main Thread (React) sẽ lấy local Y cộng với globalY của bức ảnh đó để ra được tọa độ ngắt trên toàn dải truyện ảo.

Bước 3: Render giao diện bằng Virtual Scrolling (React UI)

Đây là phần quan trọng nhất để tránh crash DOM. Bạn có thể tự code hoặc dùng thư viện như @tanstack/react-virtual hoặc react-window.

Vỏ bọc (Container): Tạo một div có overflow-y: auto.

Khối độn chiều cao (Spacer): Bên trong Container, tạo một div con có chiều cao bằng totalVirtualHeight (ví dụ: height: 50000px). Điều này giúp thanh cuộn (scrollbar) hiển thị và hoạt động chính xác như thể có một bức ảnh khổng lồ ở đó.

Render có điều kiện (Intersection/Windowing): Lắng nghe sự kiện onScroll của Container. Lấy vị trí scrollTop và chiều cao của Viewport.

Chỉ load <canvas> hoặc <img> cho những phần tử trong virtualStrip có dải globalY nằm trong vùng nhìn thấy (Viewport) + vùng đệm (buffer khoảng 1-2 viewport).

Các ảnh nằm ngoài vùng này sẽ bị unmount khỏi DOM, giải phóng hoàn toàn bộ nhớ RAM.

Bước 4: Tương tác với Ống ngắm (ViewFinder)

ViewFinder lơ lửng trên màn hình (position fixed/absolute so với Viewport, không phải so với mảng ảo).

Khi user cuộn truyện hoặc kéo ViewFinder, bạn lấy tọa độ của ViewFinder cộng với scrollTop hiện tại để ra tọa độ Y_capture trên dải truyện ảo.
