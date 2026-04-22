# V1 Ken Burns / Keyframe Motion Set Cho Export MP4

## Summary
- Giữ phạm vi ở `frontend`, chỉ nâng cấp browser render hiện tại để mỗi clip có motion cinematic mặc định thay vì frame tĩnh.
- Chốt `v1 = hard cut giữa clip + motion nội clip`, không làm crossfade/overlap, không B-roll, không subtitle animation.
- Motion mặc định là `epic vừa phải`: đủ nổi bật cho recap review truyện nhưng không quá gắt để làm mệt ở timeline dài.
- Cách triển khai chốt: bỏ mô hình “1 PNG/clip”, thay bằng render frame sequence trên canvas cho từng clip rồi encode bằng `ffmpeg.wasm`.

## Key Changes
### 1. Motion spec và types
- Mở rộng `CompiledRenderClip` với motion metadata nội bộ, tối thiểu:
  - `motionPreset`
  - `motionSeed`
  - `motionIntensity`
- Thêm một tập preset cố định, không random runtime:
  - `push_in_center`
  - `push_in_upper_focus`
  - `push_in_lower_focus`
  - `drift_left_to_right`
  - `drift_right_to_left`
  - `rise_up_focus`
  - `pull_back_reveal`
- `buildRenderPlan()` tự gán preset theo thứ tự clip bằng vòng lặp deterministic để export cùng một timeline luôn ra cùng một motion pattern.
- Không thêm control UI cho v1; motion là default behavior của export path.

### 2. Render engine
- Đổi `renderPlanToMp4()` sang pipeline per-frame:
  - preload panel image một lần cho mỗi clip
  - sinh frame PNG theo `FRAME_RATE`
  - encode segment MP4 từ image sequence + audio hiện có
  - concat tất cả segment thành 1 file MP4 cuối
- Tách `composeFrame()` thành dạng nhận `progress` 0..1 để vẽ animation theo thời gian.
- Motion cho mỗi preset dùng easing mềm, không linear thô:
  - zoom khoảng `1.04 -> 1.14`
  - pan tối đa khoảng `4% -> 9%` khung hình tùy preset
  - clip ngắn thì giảm biên độ để tránh giật
- Giữ bố cục recap hiện tại:
  - ảnh chính vẫn ở safe area dọc
  - background blur vẫn tồn tại
  - caption burned nếu bật vẫn nằm cố định, không chạy theo motion
- Thêm polish nhẹ để tạo cảm giác “epic” nhưng không thành effect nặng:
  - subtle vignette/shadow giữ focus
  - motion ease-in/ease-out
  - không dùng shake, rotation lớn, flash, hoặc parallax giả
- Cleanup toàn bộ frame files của từng clip ngay sau khi encode xong segment để tránh phình WASM FS.

### 3. Heuristic chọn preset
- Preset assignment dựa trên `orderIndex` và aspect image để tránh lặp cảm giác:
  - panel cao hoặc crop dọc: ưu tiên push-in và rise
  - panel rộng hơn: ưu tiên drift ngang và pull-back
- Hai clip liên tiếp không được dùng cùng family motion nếu còn preset khác khả dụng.
- Clip rất ngắn hoặc silent minimum clip:
  - vẫn có motion nhưng giảm intensity
  - không dùng preset drift dài gây cảm giác chưa kịp đọc đã trôi
- `holdAfterMs` vẫn được tính trong duration; motion tiếp tục chạy chậm ở tail thay vì đứng khựng.

### 4. UI/UX render step
- `StepRender` chỉ đổi copy để phản ánh export không còn là “static frames, hard cuts” mà là “cinematic keyframed panel motion”.
- Không thêm tab hay form mới.
- Render progress vẫn hiển thị theo clip, nhưng detail nên cập nhật thành kiểu:
  - `Animating clip 12/52`
  - `Encoding clip 12/52`
- Nếu render fail, lỗi trả về cần phân biệt rõ:
  - frame synthesis
  - clip encode
  - final concat

## Test Plan
- `renderPlan` test:
  - clip build ra có `motionPreset` deterministic
  - disabled clip không ảnh hưởng vòng preset
  - timeline giống nhau build nhiều lần cho preset giống nhau
- `renderEngine` test hoặc unit-level helper test:
  - preset transform ở `progress=0`, `0.5`, `1` nằm trong biên độ mong muốn
  - clip ngắn tự giảm intensity
  - caption burn-in không bị lệch khi motion chạy
- Smoke test frontend:
  - export 1 clip có audio
  - export nhiều clip mixed audio/silent
  - caption off
  - caption burned
  - timeline dài vẫn cleanup temp frames sau từng clip
- Acceptance:
  - MP4 cuối là 1 file hoàn chỉnh
  - mỗi clip có motion rõ ràng
  - không có transition overlap giữa clip
  - render không giữ toàn bộ frame sequence của mọi clip trong bộ nhớ cùng lúc

## Assumptions And Defaults
- V1 chỉ phục vụ browser export hiện tại; chưa đồng bộ spec này sang backend native render plan.
- `Hard cut + motion` là default đã khóa.
- Mức style mặc định là `epic vừa phải`.
- Không thêm UI chỉnh preset từng clip ở v1.
- Không hỗ trợ B-roll, subtitle animation, crossfade, hoặc keyframe editor ở v1.
- Nếu sau này chuyển render chính sang backend native, motion metadata hiện tại sẽ là contract nội bộ phù hợp để tái dùng ở engine mới.
