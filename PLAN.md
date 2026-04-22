# Backend Native FFmpeg Export With Browser Fallback

## Tóm tắt
- Chuyển `Export MP4` chính thức sang backend async render job dùng native `ffmpeg.exe`.
- Giữ browser-side render hiện tại làm fallback/preview phụ, không còn là đường export chính.
- Mỗi lần export, frontend gửi toàn bộ panel image + audio WAV + render plan trong một `multipart/form-data` request self-contained.
- Backend lưu asset và MP4 theo job trong thư mục tạm, phục vụ tải file kết quả theo kiểu ephemeral download rồi cleanup theo TTL.

## Thay đổi chính
- Backend thêm một render subsystem riêng, không tái dùng `JobQueue` script hiện tại.
- Tạo `RenderJobQueue` và `RenderJobRecord` riêng để tránh trộn schema, logic progress, temp file, và lifecycle với script jobs.
- Thêm `RenderService` hoặc `NativeFfmpegRenderService` chịu trách nhiệm:
  - validate render request
  - lưu panel/audio uploads theo clip
  - compose concat list
  - chạy `ffmpeg` native qua subprocess
  - cập nhật progress/log theo phase
  - xuất file MP4 cuối cùng
- Backend thêm route nhóm `/api/v1/render`:
  - `POST /api/v1/render/jobs`
  - `GET /api/v1/render/jobs/{job_id}`
  - `GET /api/v1/render/jobs/{job_id}/result`
  - `POST /api/v1/render/jobs/{job_id}/cancel`
- Frontend đổi nút chính ở tab Render sang tạo backend render job, poll progress, rồi mở preview/download khi job hoàn tất.
- Browser render hiện tại được giữ lại dưới một action phụ kiểu `Fallback browser render` hoặc `Preview in browser`, không còn là đường mặc định.
- `voice/options` và preview voice không được block export workflow; lỗi ở tab Voice không được làm hỏng backend export job path.

## API và contract cần chốt khi triển khai
- `POST /api/v1/render/jobs` dùng `multipart/form-data`.
- Form fields:
  - `plan`: JSON string
  - `clips`: JSON string metadata theo thứ tự clip active
  - `files`: list file upload, gồm cả panel images và audio WAV
- `clips` phải là contract rõ ràng, mỗi item gồm:
  - `clipId`
  - `panelId`
  - `orderIndex`
  - `durationMs`
  - `holdAfterMs`
  - `captionText`
  - `panelFileKey`
  - `audioFileKey` hoặc `null`
- `plan` gồm:
  - `outputWidth`
  - `outputHeight`
  - `captionMode`
  - `frameRate`
- Backend không tự suy luận thứ tự clip từ filename; phải dùng metadata `clips` làm source of truth.
- `GET /api/v1/render/jobs/{job_id}` trả:
  - `jobId`
  - `status`
  - `progress`
  - `phase`
  - `detail`
  - `downloadUrl` hoặc `null`
  - `error`
  - `logs`
- `GET /api/v1/render/jobs/{job_id}/result` stream `video/mp4` khi job `completed`.
- `POST /api/v1/render/jobs/{job_id}/cancel` hủy subprocess ffmpeg nếu đang chạy, cleanup temp dir, đánh dấu `cancelled`.
- Backend cần dependency check cho `ffmpeg` khi khởi tạo render service; nếu không tìm thấy binary thì `POST /render/jobs` trả `503` với message rõ ràng.
- TTL kết quả mặc định: 1 giờ kể từ lúc job hoàn tất. Sau TTL backend xóa thư mục job và file MP4.
- Frontend primary flow:
  - build backend render payload từ timeline active hiện tại
  - upload tạo job
  - poll mỗi 1 giây
  - khi `completed`, tự chuyển sang tab `Export` và gắn `previewUrl` từ backend result endpoint
  - khi `failed`, hiển thị `error` và logs backend
- Browser fallback flow:
  - chỉ xuất hiện như button phụ
  - chỉ chạy khi user chủ động chọn
  - không tự fallback âm thầm khi backend export lỗi

## Thiết kế triển khai backend
- Thêm model API riêng cho render:
  - `RenderJobCreateResponse`
  - `RenderJobStatusResponse`
  - `RenderClipSpec`
  - `RenderPlanRequest`
- Thêm model domain/job riêng cho render:
  - `RenderJobRecord`
  - `RenderJobStatus`
  - `RenderJobLogEntry`
- Thêm utility temp file riêng cho render assets và output:
  - panel files
  - audio files
  - concat manifest
  - output mp4
- Thêm `RenderService` native:
  - dựng command ffmpeg cho từng clip bằng image loop + audio input
  - với clip không có audio, synthesize silence bằng native ffmpeg
  - với `captionMode="burned"`, phase đầu dùng Python compose frame PNG có caption baked-in để giữ parity với FE hiện tại
- Progress backend chia phase cố định:
  - `accepted`
  - `preparing assets`
  - `rendering clip N/M`
  - `muxing final video`
  - `finalizing`
  - `completed`
- Queue backend nên chạy single-worker mặc định để tránh nhiều export lớn tranh CPU/disk; concurrency là config sau này nếu cần.
- Cleanup luôn chạy trong `finally`, kể cả `failed` và `cancelled`, trừ file MP4 của job `completed` còn giữ tới TTL.
- Thêm scheduler đơn giản hoặc lazy cleanup khi đọc/truy cập job list/result; không cần background cron phức tạp cho v1.

## Thiết kế triển khai frontend
- Thêm client API riêng cho backend render job.
- `StepRender` đổi `handleRender()`:
  - nếu chọn backend primary thì gọi create-job
  - lưu `jobId`
  - poll status
  - render progress card từ `phase/detail/progress`
  - khi done, dùng `/result` làm source cho `<video controls>`
- `Render MP4` button chính map sang backend export.
- Thêm button phụ `Browser Fallback` hoặc `Preview In Browser`.
- `renderError` phải hiển thị nguyên message backend, không nén về `Render failed`.
- Khi backend export đang chạy:
  - disable nút chính
  - cho phép cancel nếu user bấm `Cancel export`
  - không gọi `voice/options` hay render preview voice trong background từ tab render
- `buildRenderPlan()` hiện tại tiếp tục là source để sinh clip order/duration, nhưng cần thêm bước serialize file-key mapping cho multipart backend request.

## Test plan
- Backend route test cho `POST /render/jobs` với đủ asset hợp lệ tạo job `queued`.
- Backend route test cho mismatch giữa metadata clip và số file upload trả `400`.
- Backend service test cho missing `ffmpeg` trả `503`.
- Backend queue test cho progress phase chuyển đúng từ `queued` tới `completed`.
- Backend cancel test cho job đang chạy chuyển `cancelled` và cleanup temp dir.
- Backend result test cho job chưa xong trả `409`, job xong stream `video/mp4`.
- Backend TTL test cho output file bị xóa sau expiry hoặc khi cleanup lazy chạy.
- Frontend test cho `StepRender` polling backend status và hiển thị `renderProgress`.
- Frontend test cho success path đổi tab export và gắn `previewUrl`.
- Frontend test cho failed job hiển thị lỗi backend chi tiết.
- Frontend test cho browser fallback vẫn hoạt động độc lập.
- End-to-end scenario:
  - 1 clip có audio
  - nhiều clip có mix audio + silent clip
  - caption off
  - caption burned
  - cancel giữa lúc render clip N/M
  - backend restart giữa lúc poll job

## Giả định và default đã khóa
- Export chính thức dùng backend async job.
- Asset transfer dùng một request multipart self-contained cho mỗi lần export.
- Output là ephemeral download, TTL mặc định 1 giờ.
- Browser render được giữ lại làm fallback/preview phụ, không phải primary path.
- Native `ffmpeg.exe` trên backend là dependency bắt buộc của official export.
- V1 không làm persistent render history, không làm shared asset staging, không làm distributed queue.
- V1 dùng single render worker mặc định để ưu tiên ổn định hơn throughput.
