# Upgrade Character System Theo 4 Phase

## Summary

Hiện tại repo đang ở **Phase 0.5, chưa đạt Phase 1**.

Đã có scaffold hybrid detector, HDBSCAN, crop kind, split/manual review, cache version-aware. Nhưng chất lượng vẫn thấp vì:

- `heuristic` vẫn có thể tạo cluster và `auto_confirmed` nếu confidence đủ cao.
- Anime face/head mới là adapter optional, chưa có runtime/provider ổn định được test như đường chính.
- Embedding hiện là handcrafted OpenCV descriptor, chưa có learned embedding.
- Chưa có cast-anchor propagation thật sự, chỉ có manual constraint giữ lại một phần khi rerun.

Đánh giá hiện tại: **khoảng 4.5/10**. Lý do chính là hệ thống vẫn dựa nhiều vào heuristic crop + handcrafted descriptor, nên dễ merge nhầm nhiều nhân vật.

## Phase 1: Chặn Heuristic Auto Cluster, Mục Tiêu 6/10

- Sửa clustering policy để `heuristic` không bao giờ tạo `auto_confirmed`.
- `heuristic` crop vẫn được detect và hiển thị trong review UI, nhưng chỉ được phép là `suggested` hoặc `unknown`.
- Nếu cluster chỉ có heuristic anchors, cluster đó là review-only:
  - không ghi `panelCharacterRefs` confirmed
  - không đi vào script context
  - luôn có `review_needed` hoặc `weak_identity_signal`
- Face/head vẫn được phép auto-confirm theo threshold rất cao.
- Person/body/accessory tiếp tục chỉ là context metadata, không tạo identity chính.

Acceptance:

- Case “nhân vật 1 có 8 panels nhưng merge quá nhiều người” phải chuyển phần lớn sang `suggested/unknown`, không còn auto-confirm cả cụm.
- Script context không nhận bất kỳ cluster nào chỉ dựa trên heuristic.
- UI vẫn thấy đầy đủ crop/panel để user split/lock thủ công.

## Phase 2: Anime Face/Head Chạy Ổn, Mục Tiêu 7.5/10

- Biến anime face/head detector thành đường identity chính, không chỉ optional best-effort.
- Giữ provider optional để backend không crash, nhưng thêm runtime diagnostics rõ:
  - provider loaded hay không
  - model path
  - device
  - số face/head crop detect được
  - fallback reason nếu fail
- Chỉ cho `face/head` crop làm identity anchor auto.
- Face bbox sinh thêm `head` crop bằng expansion heuristic, nhưng head derived phải lưu `derivedFrom=face`.
- Thêm warmup/test path cho detector:
  - ảnh synthetic hoặc fixture anime face/head
  - xác nhận detect được face/head
  - xác nhận thiếu dependency/model thì fallback OpenCV nhưng không crash
- UI hiển thị rõ crop `kind=face/head` để user biết cluster dựa trên tín hiệu nào.

Default:

- `AI_BACKEND_CHARACTER_DETECTOR_MODE=hybrid`
- Nếu anime provider fail, hệ thống vẫn chạy nhưng chất lượng chỉ đạt Phase 1, diagnostics phải nói rõ.

## Phase 3: Cast-Anchor Propagate, Mục Tiêu 8.5/10

- Thêm anchor bank từ các cluster đã `locked` hoặc manual split/rename.
- Anchor bank lấy vector từ crop đã lock trước đó, ưu tiên `face/head`; heuristic manual anchor chỉ dùng để suggest, không auto-confirm.
- Khi rerun prepass:
  - load anchor bank từ previous state
  - match crop face/head mới với anchor bank trước hoặc sau HDBSCAN
  - nếu similarity cao và margin rõ, gán vào cluster locked cũ
  - giữ nguyên canonical name, lockName, cluster id nếu có thể
- Không cho auto merge hai locked clusters khác nhau.
- Nếu một crop match nhiều locked anchors gần nhau, chuyển `suggested` và gắn review flag `anchor_conflict`.
- Split/rename/lock trở thành constraint bền:
  - rerun không được merge ngược cluster đã split
  - panel refs manual vẫn thắng crop state unknown/suggested

Acceptance:

- User split một nhân vật ra cluster mới, rerun prepass không gộp ngược lại.
- Nhân vật chính đã lock tiếp tục propagate qua panel mới nếu có face/head tương đồng.
- Conflict giữa hai nhân vật locked không auto-resolve.

## Phase 4: Learned Embedding DINOv2 Local, Mục Tiêu 9/10

- Thêm learned embedder local bằng **DINOv2 local** làm provider mặc định cho Phase 4.
- Không tự download model trong runtime.
- Chỉ bật learned embedding khi model path tồn tại local.
- Config mới:
  - `AI_BACKEND_CHARACTER_EMBEDDER=hybrid-dinov2`
  - `AI_BACKEND_CHARACTER_DINO_MODEL_PATH=<local path>`
  - `AI_BACKEND_CHARACTER_EMBED_DEVICE=auto`
- Embedding mới là hybrid vector:
  - DINOv2 image embedding là tín hiệu chính
  - handcrafted descriptor vẫn giữ làm phụ trợ
  - crop kind feature vẫn giữ
- Cache key phải gồm:
  - embedder provider
  - DINO model path/hash
  - device
  - crop kind
  - detector version/config
- Similarity policy tách theo kind:
  - face/head dùng threshold cao nhất
  - body/upper_body chỉ suggest
  - accessory không được tạo identity
- Thêm batch embedding để tránh chậm khi nhiều crop.

Acceptance:

- Same character khác nền/pose nhẹ vẫn group tốt hơn handcrafted.
- Hai nhân vật mặc đồ giống nhưng mặt/head khác không auto-merge.
- Learned model thiếu file local thì backend fallback handcrafted và ghi diagnostics rõ.

## Test Plan

- Phase 1 tests:
  - heuristic-only crop không tạo `auto_confirmed`
  - heuristic-only cluster không đi vào script context
  - mixed panel mơ hồ vẫn unresolved/suggested
  - existing manual split/lock vẫn hoạt động

- Phase 2 tests:
  - anime provider loaded thì tạo crop `face/head`
  - anime provider missing thì fallback OpenCV không crash
  - face/head crop được auto-confirm khi similarity cao
  - face conflict không bị body/clothes override

- Phase 3 tests:
  - locked cluster propagate qua rerun
  - split cluster không merge ngược
  - anchor conflict sinh review flag, không auto-confirm
  - manual panel override vẫn không bị unresolved

- Phase 4 tests:
  - DINOv2 model path missing thì fallback handcrafted
  - DINOv2 cache invalid khi model hash/provider đổi
  - learned embedding giảm false merge trong regression “nhân vật 1 merge 8 panels”
  - batch embedding output ổn định CPU/GPU

## Assumptions

- Ưu tiên chất lượng identity hơn recall tự động.
- Phase 1 cố ý làm conservative: ít auto-confirm hơn, nhiều review hơn.
- `heuristic` chỉ còn là UI/review signal, không là identity confirmation signal.
- DINOv2 local là lựa chọn chính cho Phase 4 theo quyết định hiện tại.
- Không model nào được tự download trong request runtime.
- Script context chỉ nhận `auto_confirmed` từ face/head/cast-anchor hoặc `manual`, không nhận `suggested`.
