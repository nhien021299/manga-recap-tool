# Upgrade Character System: Local Hybrid Detector + HDBSCAN

## Summary
Nâng character system từ heuristic OpenCV hiện tại sang pipeline local hybrid: anime face/head detection làm tín hiệu chính, object/body fallback làm tín hiệu phụ, embedding tách theo loại crop, HDBSCAN để giảm merge quá tay, và UI review/split để sửa các cluster còn mơ hồ. Mặc định chạy CPU-safe vì runtime hiện tại là `torch 2.11.0+cpu`, CUDA `false`; nếu sau này có GPU thì dùng `auto`.

## Key Changes
- Backend prepass chuyển version lên `character-hybrid-v3`, tự invalidate cache cũ.
- Thêm cấu hình:
  - `AI_BACKEND_CHARACTER_DETECTOR_MODE=hybrid`
  - `AI_BACKEND_CHARACTER_DEVICE=auto`
  - `AI_BACKEND_CHARACTER_CLUSTERER=hdbscan`
  - `AI_BACKEND_CHARACTER_OBJECT_MODEL=yolov8n.pt`
  - `AI_BACKEND_CHARACTER_MIN_CLUSTER_SIZE=2`
- Thêm dependency backend trực tiếp:
  - `scikit-learn` explicit, vì repo đang import `sklearn` nhưng chưa khai báo.
  - `ultralytics` cho object/person fallback.
  - anime face detector là optional runtime provider; backend không được crash nếu thiếu model/dependency, chỉ fallback OpenCV và ghi diagnostics.
- Giữ OpenCV detector hiện tại làm fallback cuối cùng, không xóa.

## Implementation Changes
- Detector layer:
  - Tạo detector abstraction trả về crop candidates có `kind`: `face`, `head`, `upper_body`, `person`, `accessory`, `heuristic`.
  - Primary: anime face/head detector để bắt mặt/đầu nhân vật.
  - Secondary: YOLO/object detector local cho `person/upper body` và object hints; accessory chỉ là metadata, không được tự merge identity.
  - Fallback: OpenCV `heuristic-multi-crop-v1`.
  - Với face bbox, sinh thêm head/hair-region crop bằng expansion heuristic để tăng stability khi mặt nhỏ hoặc che một phần.
- Embedding layer:
  - Tách vector thành weighted hybrid descriptor: face/head embedding trọng số cao nhất, body/clothing trung bình, accessory thấp nhất.
  - Giữ handcrafted descriptors hiện tại làm visual descriptors phụ.
  - Cache key phải bao gồm detector mode, detector versions, crop kind, model path, device, và embedder version.
- Clustering:
  - Thay default agglomerative bằng HDBSCAN qua `sklearn.cluster.HDBSCAN`.
  - HDBSCAN chỉ auto-confirm cluster khi có đủ mật độ và confidence; noise thành `unknown`, không ép vào cluster gần nhất.
  - Nearest-neighbor attach chỉ sinh `suggested`, không sinh `auto_confirmed`, trừ khi face/head similarity vượt ngưỡng rất cao và margin rõ.
  - Không cho accessory-only hoặc body-only match tạo merge tự động.
- Review/API/UI:
  - Thêm endpoint `POST /api/v1/characters/split` nhận `chapterId`, `sourceClusterId`, `cropIds`, `panelIds`, `canonicalName?`; tạo cluster mới và rebuild refs.
  - UI Character Review hiển thị rõ crop kind, score, assignment state, panel refs, và nút split selected crops/panels.
  - Manual rename/lock/split trở thành constraint: lần re-run sau không được tự merge ngược vào cluster khác nếu user đã lock.

## Test Plan
- Unit tests:
  - Detector fallback: thiếu anime detector hoặc YOLO thì prepass vẫn chạy bằng OpenCV.
  - HDBSCAN noise: crop mơ hồ không bị ép vào cluster.
  - Face conflict: hai face/head khác nhau không auto-merge dù body/clothes giống.
  - Accessory-only match không tạo auto-confirm.
  - Split endpoint chuyển crop/panel sang cluster mới và rebuild `panelCharacterRefs`.
- Regression tests:
  - Case hiện tại “nhân vật 1 merge quá nhiều nhân vật khác nhau” phải giảm xuống: cluster mơ hồ chuyển thành `unknown/suggested` thay vì một cluster 8 panel.
  - Existing tests cho blank panel, multiple characters in one panel, force rerun, cache invalidation vẫn pass.
- Manual acceptance:
  - Character UI phải cho thấy đầy đủ panel/crop trong cluster.
  - User có thể split các panel sai ra nhân vật mới mà không cần xóa cache thủ công.
  - Script context chỉ nhận refs `auto_confirmed` hoặc `manual`, không nhận `suggested`.

## Assumptions
- Chọn hướng **max quality local** và chấp nhận dependency nặng.
- Runtime mặc định CPU, GPU chỉ dùng khi `torch.cuda.is_available()`.
- Anime face detector là provider optional để tránh làm backend không khởi động được trên Windows/Python 3.12 nếu dependency nặng lỗi build.
- YOLO general model chỉ dùng làm body/person fallback; accessory/hair/cloak nếu không có custom model thì chỉ là best-effort metadata, không dùng làm identity chính.

Sources considered for dependency direction: anime-face-detector repo https://github.com/hysts/anime-face-detector, scikit-learn HDBSCAN docs https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html, Ultralytics docs https://docs.ultralytics.com/.
