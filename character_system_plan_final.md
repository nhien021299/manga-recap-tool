# Final Plan - Character Consistency System for manga-recap-tool

## 1. Mục tiêu

Xây dựng một **Character Consistency Step** đứng trước bước Script Generation để giải quyết triệt để tình trạng:

- cùng một nhân vật bị gọi bằng nhiều tên khác nhau trong cùng chapter,
- model đổi cách xưng hô theo từng panel cục bộ,
- script thiếu sự ổn định và giảm cảm giác “chuyên nghiệp” khi nghe recap.

Hệ này phải đạt các tiêu chí sau:

1. **Kết quả đủ tốt để dùng thật ngay**
2. **Giảm dữ liệu bẩn và giảm merge nhầm**
3. **Không làm pipeline chậm đi quá nhiều**
4. **Không phụ thuộc vào vision LLM trên đường chính**
5. **Cho phép user khóa tên nhân vật một lần và tái sử dụng nhất quán**
6. **Mở đường sạch cho memory xuyên nhiều chapter về sau**

---

## 2. Kết luận chiến lược

Sweet spot tối ưu cho tool hiện tại là:

**Face/Head Detect -> Quality Filter -> Embedding -> Conservative Clustering -> Character Review -> Name Lock -> Inject Character Mapping vào Script**

Đây là hướng cân bằng tốt nhất giữa:

- độ ổn định,
- thời gian xử lý,
- mức độ dễ build,
- khả năng debug,
- chi phí triển khai thực tế.

### Những gì sẽ KHÔNG dùng trên đường chính

Để giữ đúng sweet spot, hệ thống **không dùng** các hướng sau cho production Phase 1:

- vision LLM để mô tả từng panel,
- tracker kiểu video MOT như ByteTrack / BoT-SORT,
- ensemble nhiều detector,
- nhiều embedding model xếp chồng,
- auto naming hoàn toàn không cần user,
- pipeline quá nặng để xử lý các case cực khó ngay từ đầu.

Lý do rất rõ: các hướng này làm tăng độ phức tạp và thời gian chạy nhanh hơn lợi ích mà chúng mang lại trong giai đoạn hiện tại.

---

## 3. Vấn đề cốt lõi cần sửa

Ví dụ hiện tại:

- panel 1: model gọi là **"gã trai trẻ"**
- panel 4: cùng người đó lại bị gọi là **"gã hái thuốc"**
- panel 9: lại thành **"thanh niên mang giỏ"**

Đây không phải lỗi “văn phong”, mà là lỗi **thiếu lớp định danh nhân vật**.

### Kết luận quan trọng

Không giải bài toán này bằng cách nhồi prompt dài hơn.

Muốn ổn định thật, hệ phải:

1. nhận diện cùng một người qua nhiều panel,
2. gán họ vào một cluster danh tính,
3. cho user đặt **canonical name**,
4. ép bước Script dùng đúng canonical name đó.

Consistency phải đến từ **data layer**, không đến từ việc hy vọng model “nhớ” tốt hơn.

---

## 4. Phạm vi triển khai

## 4.1 Phase mục tiêu chính

### Phase 1
Tập trung giải quyết **within-chapter consistency**:

- nhận diện nhân vật trong một chapter,
- gom các lần xuất hiện của cùng một người,
- cho user đặt tên một lần,
- giữ tên đó xuyên suốt chapter,
- inject mapping vào step Script.

### Phase 2
Mở rộng lên **cross-chapter memory**:

- tái sử dụng lại nhân vật ở các chapter sau,
- cho phép user chỉ đặt tên một lần rồi dùng lâu dài.

### Phase 3
Tối ưu dần cho các case khó:

- ít thấy mặt,
- nhiều góc nghiêng,
- biến đổi outfit,
- action panel méo hình.

---

## 5. Kiến trúc tổng thể

```text
Frontend Extract Panels
    ->
Backend Character Prepass
    1. detect face/head
    2. quality score
    3. embedding
    4. conservative clustering
    5. build character cards
    ->
Frontend Character Review
    6. rename / lock / merge / ignore / unknown
    ->
Backend Script Payload Builder
    7. inject panel_character_refs + canonical names
    ->
Script Generation
    8. model bắt buộc dùng canonical name nếu có
```

---

## 6. Sweet spot triển khai được chọn

## 6.1 Detector
Dùng **một detector face/head nhẹ và ổn định** làm baseline production.

### Lý do
- nhanh hơn,
- ít dependency,
- dễ maintain,
- đủ cho đa số panel có mặt tương đối rõ.

### Quy tắc chọn
Không bench vô hạn. Chỉ test **một lần nghiêm túc** trên 3 chapter mẫu:

1. chapter sáng, mặt rõ,
2. chapter nhiều góc nghiêng / combat,
3. chapter tối / horror / panel méo.

Sau benchmark:
- chốt **một detector duy nhất** cho production,
- không đổi qua lại liên tục.

### Chính sách
- nếu detector baseline đủ dùng: giữ nguyên,
- nếu miss quá nhiều: mới nâng cấp sang detector tốt hơn,
- không mở nhiều nhánh detector song song.

---

## 6.2 Embedding
Dùng **một embedding model duy nhất** để chuyển crop mặt / đầu thành vector số.

### Vai trò
Embedding là thứ giúp hệ trả lời câu hỏi:

> crop này có giống crop kia đủ để xem là cùng một nhân vật không?

### Chính sách
- chỉ dùng **một model**,
- không ensemble,
- không kéo vision LLM vào bước này,
- giữ output embedding ổn định và dễ cache.

---

## 6.3 Clustering
Dùng **Agglomerative Clustering** làm mặc định cho Phase 1.

### Vì sao chọn Agglomerative
- dễ hiểu,
- dễ tune,
- dễ debug,
- dễ kiểm soát ngưỡng merge,
- hợp với bài toán chapter manga cỡ vừa.

### Vì sao chưa dùng HDBSCAN ngay
HDBSCAN mạnh với outlier nhưng khó tune hơn ở vòng đầu. Nó chỉ nên là **phương án nâng cấp** nếu benchmark thật cho thấy:

- quá nhiều crop rác,
- quá nhiều case ambiguous,
- agglomerative merge nhầm thường xuyên.

### Kết luận
- **Phase 1 default:** Agglomerative
- **Phase 1.5 optional:** HDBSCAN nếu dữ liệu thực tế buộc phải nâng

---

## 6.4 Descriptor phụ
Không dùng vision LLM trên đường chính.

Thay vào đó, dùng các descriptor nhẹ để hỗ trợ cluster và UI:

- hair tone bucket,
- outfit tone bucket,
- crop size,
- crop ratio,
- panel index / page order,
- accessory hint đơn giản nếu trích được.

### Vai trò descriptor phụ
Descriptor phụ không dùng để “hiểu truyện”, mà chỉ để:

- hỗ trợ phân biệt cluster khi embedding chưa đủ chắc,
- tạo preview label cho user,
- tăng độ tin cậy cho những case biên.

### Nguyên tắc
Descriptor phụ là **support feature**, không được override embedding nếu tín hiệu không đủ mạnh.

---

## 7. Nguyên tắc chống dữ liệu bẩn

Đây là phần quan trọng nhất của toàn plan.

### Triết lý chung
**Thà split thừa còn hơn merge nhầm.**

Merge nhầm 2 nhân vật thành một sẽ làm script sai tên xuyên chapter và cực khó chịu.  
Split thừa thì user chỉ cần merge lại vài cluster bằng UI.

---

## 7.1 Quality Gate
Trước khi một crop được dùng cho cluster, crop đó phải qua quality gate.

### Tiêu chí tối thiểu
- kích thước crop đủ lớn,
- confidence detect đủ cao,
- không quá mờ,
- không quá méo,
- không bị che khuất nặng,
- không chỉ còn fragment quá nhỏ.

### Hành vi
- crop đạt chuẩn -> dùng cho embedding và có thể làm anchor
- crop yếu -> vẫn lưu metadata nhưng không được làm anchor chính
- crop quá xấu -> loại khỏi pipeline nhận diện

---

## 7.2 Anchor-first Policy
Mỗi cluster phải có một nhóm **anchor crops** là các crop tốt nhất của cluster đó.

### Mục tiêu
- cluster được đại diện bởi dữ liệu sạch hơn,
- giảm hiệu ứng “rác kéo rác”,
- tăng độ ổn định khi gán các crop biên.

### Quy tắc
- chỉ 3 đến 8 crop tốt nhất được dùng làm anchor,
- crop chất lượng thấp chỉ được attach vào cluster khi similarity cao rõ ràng.

---

## 7.3 Conservative Merge
Hệ không được merge quá hăng.

### Chính sách
- điểm similarity cao mới được auto-merge,
- vùng lưng chừng chỉ gắn cờ review,
- điểm thấp thì để unknown hoặc tách riêng.

### Hệ quả mong muốn
- giảm merge nhầm,
- tăng số split thừa vừa phải,
- user sửa ít nhưng sửa “đúng chỗ”.

---

## 7.4 Unknown-first Policy
Nếu panel không đủ dữ liệu để chắc chắn đó là ai, hệ phải ưu tiên:

**unknown > đoán bừa**

### Các trường hợp để unknown
- không thấy mặt rõ,
- crop quá bé,
- quay lưng hoàn toàn,
- chỉ lộ tóc hoặc silhouette yếu,
- action panel biến dạng mạnh.

### Lợi ích
- tránh lan truyền sai nhãn,
- giữ hệ sạch hơn,
- giảm việc sửa hỏng nhiều bước sau.

---

## 8. Kiến trúc dữ liệu

## 8.1 Entity chính

### `chapter_character_cluster`
Đại diện cho một nhân vật trong một chapter.

```json
{
  "cluster_id": "char_007",
  "chapter_id": "chapter_12",
  "status": "draft",
  "canonical_name": "gã hái thuốc",
  "display_label": "nam trẻ, mang giỏ",
  "lock_name": true,
  "confidence_score": 0.88,
  "face_count": 14,
  "anchor_crop_ids": ["crop_11", "crop_21", "crop_44"],
  "sample_panel_ids": ["panel_03", "panel_07", "panel_16"],
  "created_at": "2026-04-24T12:00:00Z",
  "updated_at": "2026-04-24T12:15:00Z"
}
```

### `character_crop`
Một crop mặt / đầu phát hiện từ panel.

```json
{
  "crop_id": "crop_21",
  "chapter_id": "chapter_12",
  "panel_id": "panel_07",
  "bbox": [120, 40, 220, 180],
  "detect_confidence": 0.93,
  "quality_score": 0.86,
  "embedding_path": "cache/embeddings/ch12/crop_21.npy",
  "is_anchor_candidate": true,
  "assigned_cluster_id": "char_007"
}
```

### `panel_character_candidate`
Ứng viên nhân vật xuất hiện trong panel.

```json
{
  "panel_id": "panel_07",
  "candidate_cluster_id": "char_007",
  "score": 0.83,
  "assignment_state": "auto"
}
```

### `panel_character_ref`
Mapping cuối cùng đã được xác nhận để gửi sang bước Script.

```json
{
  "panel_id": "panel_07",
  "cluster_ids": ["char_007"],
  "source": "auto_confirmed"
}
```

### `global_character_memory` (Phase 2)
Đại diện cho nhân vật xuyên nhiều chapter.

```json
{
  "global_character_id": "gchar_002",
  "canonical_name": "Lâm",
  "aliases": ["gã hái thuốc"],
  "visual_notes": ["giỏ thuốc", "áo tối", "nam trẻ"],
  "linked_clusters": ["chapter_12:char_007", "chapter_13:char_002"]
}
```

---

## 8.2 Định dạng lưu trữ đề xuất

### Phase 1
Dùng **SQLite + file cache** là sweet spot tốt nhất.

#### SQLite dùng để lưu
- chapter_character_cluster
- panel_character_candidate
- panel_character_ref
- review actions của user
- canonical names
- merge history
- ignore history

#### File cache dùng để lưu
- crop images
- embedding vectors
- benchmark snapshots

### Lý do chọn SQLite
- nhẹ,
- dễ ship,
- không cần infra mới,
- đủ khỏe cho bài toán này,
- dễ query và debug.

---

## 9. Flow xử lý backend chi tiết

## 9.1 Input
Backend nhận danh sách panel đã extract.

### Input tối thiểu
- `chapter_id`
- danh sách panel image paths / URLs / binary refs
- panel order

---

## 9.2 Bước 1: Detect Face/Head
Chạy detector trên toàn bộ panel.

### Output
- bbox
- confidence
- crop
- metadata panel tương ứng

### Quy tắc
- chỉ chạy **một pass**
- không cascade nhiều detector ở Phase 1
- fail ở panel nào thì ghi nhận và đi tiếp

---

## 9.3 Bước 2: Quality Scoring
Mỗi crop được chấm điểm chất lượng.

### Inputs cho quality score
- detect confidence,
- kích thước crop,
- tỷ lệ crop,
- độ rõ tương đối,
- mức che khuất ước lượng,
- khoảng trắng / nền quá nhiều.

### Output
- `quality_score`
- `quality_bucket`: good / medium / poor

### Chính sách
- good -> có thể làm anchor
- medium -> dùng để gán thêm vào cluster
- poor -> chỉ lưu metadata hoặc bỏ qua

---

## 9.4 Bước 3: Embedding
Sinh embedding cho tất cả crop đủ chuẩn.

### Chính sách hiệu năng
- cache theo `chapter_id + crop_hash`
- không re-embed nếu crop không đổi
- không chạy lặp lại nếu user chỉ đổi tên

### Output
- file vector
- embedding dimension metadata
- checksum để cache ổn định

---

## 9.5 Bước 4: Clustering
Chạy Agglomerative trên tập embeddings sạch.

### Inputs
- embedding vectors của crop good + medium
- trọng số phụ nếu có descriptor

### Chính sách
- conservative threshold
- thiên về tách cluster hơn là nhập cluster

### Output
- cluster assignments sơ bộ
- outlier / unknown group
- confidence cluster-level

---

## 9.6 Bước 5: Character Card Build
Tạo card hiển thị cho UI.

### Mỗi card gồm
- 1 thumbnail đại diện
- 3 tới 8 anchor crops
- số lần xuất hiện
- panel đầu tiên xuất hiện
- display label auto
- confidence
- flags:
  - low_confidence
  - possible_merge
  - likely_unknown

---

## 9.7 Bước 6: Panel-to-Character Mapping
Gán cluster vào từng panel.

### Hành vi
- panel có 1 nhân vật rõ -> map thẳng
- panel có nhiều crop -> map nhiều cluster
- panel mơ hồ -> unknown hoặc suggested only

### Chính sách
- mapping phải có confidence
- mapping dùng cho Script phải tách riêng với “candidate suggestions”

---

## 10. UI Review Step

Thêm một step mới vào editor:

**Extract -> Characters -> Script -> Voice -> Export**

---

## 10.1 Mục tiêu UX
UI không được biến thành chỗ bắt user soi từng panel.

User chỉ nên đụng tay vào:
- cluster chưa lock tên,
- cluster confidence thấp,
- cluster nghi có thể merge,
- panel ambiguous cần chỉnh.

---

## 10.2 Màn hình chính Character Review

### Khu vực 1: Character List
Mỗi item hiển thị:
- thumbnail cluster,
- tên hiện tại,
- số lần xuất hiện,
- confidence,
- tag trạng thái:
  - locked
  - review needed
  - unknown
  - merged

### Action trên từng character
- Rename
- Lock name
- Merge with another cluster
- Ignore
- Mark as unknown
- Open details

---

## 10.3 Khu vực 2: Character Detail
Khi mở chi tiết một cluster, hiển thị:
- 3 tới 8 anchor crops
- timeline panel xuất hiện
- panel đầu tiên xuất hiện
- panel mới nhất xuất hiện
- display label auto
- candidate merge suggestions

### Action
- xác nhận cluster đúng
- rename
- lock
- merge
- bỏ một số crop nhiễu ra khỏi cluster

---

## 10.4 Khu vực 3: Panel Inspector
Khi user click một panel:
- hiển thị panel đó map vào cluster nào,
- confidence từng mapping,
- các candidate khác nếu có,
- cho phép đổi cluster hoặc set unknown.

---

## 10.5 UX Rule quan trọng
Không ép user review mọi cluster trước khi qua step Script.

### Chỉ bắt review khi
- cluster chưa có tên và confidence thấp,
- cluster có cờ possible_merge,
- panel chứa mapping đỏ,
- cluster bị xung đột tên.

Điều này giúp flow vẫn nhanh và không phá trải nghiệm edit.

---

## 11. Naming System

## 11.1 Thứ tự ưu tiên tên
1. `canonical_name` do user đặt
2. `canonical_name` từ global memory
3. `display_label` auto-generated
4. generic fallback label

---

## 11.2 Quy tắc auto display label
Label tự sinh phải:
- ngắn,
- ổn định,
- không bay bướm,
- không thay đổi từ đồng nghĩa lung tung.

### Ví dụ tốt
- gã hái thuốc
- thiếu nữ áo trắng
- lão già tóc bạc
- kiếm sĩ mắt sẹo

### Ví dụ không tốt
- chàng trai trẻ với gương mặt đầy mệt mỏi đang cầm giỏ thuốc

### Rule
- tối đa 2 đến 4 token mô tả chính
- ưu tiên đặc điểm bám lâu:
  - đạo cụ
  - outfit
  - tóc
  - silhouette dễ nhớ

---

## 11.3 Canonical Name Lock
Khi user đã bật `lock_name = true`:
- Script step phải luôn dùng tên đó,
- không được tự đổi sang mô tả khác,
- alias chỉ dùng nội bộ, không được phát tán ra script nếu đã khóa tên.

---

## 12. Tích hợp với Step Script

## 12.1 Dữ liệu thêm vào payload
Payload gửi sang Script phải kèm:

```json
{
  "characters": [
    {
      "cluster_id": "char_007",
      "canonical_name": "gã hái thuốc",
      "display_label": "nam trẻ, mang giỏ",
      "lock_name": true
    }
  ],
  "panel_character_refs": {
    "panel_03": ["char_007"],
    "panel_07": ["char_007"]
  }
}
```

---

## 12.2 Prompt Contract bắt buộc
Prompt thêm vào bước Script chỉ cần ngắn và rõ:

```text
Character consistency rules:
- If a panel references a character with a canonical name, always use that canonical name.
- Do not rename the same character with a new descriptive label.
- If no canonical name exists, use the provided display label consistently.
- Only invent a new generic description when no character mapping is available.
```

### Ý nghĩa
- consistency do data layer kiểm soát,
- prompt chỉ là luật ngắn để model tuân thủ mapping,
- tránh prompt phình.

---

## 12.3 Cách model nên xưng hô lần đầu
Khi một nhân vật đã có canonical name:
- dùng canonical name ngay từ lần đầu nếu chapter đã lock
- không cần model tự “sáng tác lại” phần giới thiệu

Khi một nhân vật chưa có canonical name:
- dùng display label ngắn và giữ nguyên xuyên suốt chapter
- không đổi synonym theo từng panel

---

## 13. Chính sách threshold

Mục tiêu của threshold policy là **giảm thử nhiều lần**.

Không dùng quá nhiều tham số khó hiểu. Chỉ chia thành 3 vùng:

### Green Zone
- score rất cao
- auto assign
- không cần user can thiệp

### Yellow Zone
- score trung bình
- suggest assignment
- gắn cờ review

### Red Zone
- score thấp hoặc mâu thuẫn
- set unknown hoặc giữ cluster riêng

### Quy tắc vận hành
- green ít nhưng chắc,
- yellow vừa đủ để user xử lý nhanh,
- red không đoán bừa.

---

## 14. Cache Strategy

Đây là điều bắt buộc để step này không bị chậm vô ích.

## 14.1 Cần cache những gì
- detect results
- crop files
- quality scores
- embedding vectors
- clustering result
- user review state
- canonical names
- merge decisions

---

## 14.2 Khi nào KHÔNG re-run
Không re-run detect/embed/cluster nếu user chỉ:
- đổi tên,
- lock tên,
- merge cluster bằng tay,
- ignore cluster,
- chỉnh mapping panel.

### Khi nào cần re-run
Chỉ re-run nếu:
- panel source thay đổi,
- extract thay đổi,
- chapter bị re-import,
- detector/model version thay đổi,
- cache invalidated thủ công.

---

## 15. API thiết kế đề xuất

## 15.1 Prepass character
### `POST /api/v1/characters/prepass`
Chạy detect -> quality -> embedding -> clustering.

#### Request
```json
{
  "chapter_id": "chapter_12",
  "panels": [
    {"panel_id": "panel_01", "image_url": "..."},
    {"panel_id": "panel_02", "image_url": "..."}
  ]
}
```

#### Response
```json
{
  "chapter_id": "chapter_12",
  "clusters": [...],
  "panel_character_candidates": [...],
  "needs_review": true
}
```

---

## 15.2 Get character review data
### `GET /api/v1/characters/review/{chapter_id}`

Trả về:
- cluster list,
- anchors,
- candidates,
- panel mappings,
- review flags.

---

## 15.3 Rename / lock
### `POST /api/v1/characters/rename`

```json
{
  "chapter_id": "chapter_12",
  "cluster_id": "char_007",
  "canonical_name": "gã hái thuốc",
  "lock_name": true
}
```

---

## 15.4 Merge clusters
### `POST /api/v1/characters/merge`

```json
{
  "chapter_id": "chapter_12",
  "source_cluster_id": "char_011",
  "target_cluster_id": "char_007"
}
```

---

## 15.5 Update panel mapping
### `POST /api/v1/characters/panel-mapping`

```json
{
  "chapter_id": "chapter_12",
  "panel_id": "panel_07",
  "cluster_ids": ["char_007"]
}
```

---

## 15.6 Export script-ready character data
### `GET /api/v1/characters/script-context/{chapter_id}`

Trả về đúng format cần inject vào Script step:
- characters
- panel_character_refs
- locked names
- unknown flags

---

## 16. Cấu trúc module đề xuất

## 16.1 Backend
Đề xuất thêm nhóm module riêng:

```text
backend/app/services/characters/
    detector.py
    quality.py
    embedder.py
    cluster.py
    labeling.py
    review_state.py
    script_context.py
```

### Vai trò từng file
- `detector.py`: detect face/head và cắt crop
- `quality.py`: score chất lượng crop
- `embedder.py`: sinh embedding và cache
- `cluster.py`: gom cluster + scoring
- `labeling.py`: sinh display label auto
- `review_state.py`: lưu rename / merge / ignore / lock
- `script_context.py`: build payload cuối cho step Script

---

## 16.2 API layer
```text
backend/app/api/v1/characters.py
```

Chứa các route character đã nêu ở phần API.

---

## 16.3 Frontend
Đề xuất thêm:

```text
web-app/src/features/characters/
    api.ts
    types.ts
    CharacterReviewStep.tsx
    CharacterList.tsx
    CharacterDetail.tsx
    PanelInspector.tsx
```

### Vai trò
- `api.ts`: gọi route backend
- `types.ts`: định nghĩa cluster / mapping / review model
- `CharacterReviewStep.tsx`: màn tổng
- `CharacterList.tsx`: danh sách cluster
- `CharacterDetail.tsx`: xem anchor và merge
- `PanelInspector.tsx`: sửa mapping theo panel

---

## 17. Rollout Plan

## Phase 1A - MVP usable
### Build
- face/head detect
- quality filter
- embedding
- agglomerative clustering
- character review UI cơ bản
- rename + lock
- script payload injection

### Kết quả kỳ vọng
- giảm mạnh việc một nhân vật bị gọi bằng nhiều tên trong cùng chapter
- user chỉ cần review nhanh rồi generate script

---

## Phase 1B - Hardening
### Build
- anchor selection tốt hơn
- candidate merge suggestions
- unknown handling sạch hơn
- cache ổn hơn
- benchmark detector chính thức để khóa production

### Kết quả kỳ vọng
- ít sửa tay hơn
- ít cluster bẩn hơn

---

## Phase 2 - Cross-chapter Memory
### Build
- global character memory
- link cluster cũ và mới
- auto-suggest nhân vật cũ
- alias history
- first appearance tracking

### Kết quả kỳ vọng
- đặt tên một lần, reuse cho chapter sau

---

## 18. Benchmark và Acceptance Criteria

## 18.1 Benchmark dataset nội bộ
Chuẩn bị 3 đến 5 chapter mẫu:

1. chapter dễ,
2. chapter combat,
3. chapter horror / dark,
4. chapter nhiều nhân vật phụ,
5. chapter nhiều crop nhỏ.

### Không cần benchmark vô hạn
Chỉ cần bộ benchmark cố định để:
- chọn detector,
- chốt threshold,
- so sánh trước và sau.

---

## 18.2 Chỉ số đánh giá chính
### Functional
- cluster list xuất hiện đúng trong UI
- user rename / lock / merge được
- payload Script có panel_character_refs hợp lệ
- script dùng đúng canonical name

### Quality
- giảm rõ rệt việc đổi tên cùng một nhân vật trong cùng chapter
- merge nhầm ít hơn split thừa
- unknown được dùng đúng chỗ, không đoán quá tay

### Performance
- character step không trở thành bottleneck chính
- đổi tên không làm re-run preprocessing

### UX
- user không phải kiểm từng panel
- user chỉ cần sửa số ít case ambiguity

---

## 19. Rủi ro và cách chặn

## Rủi ro 1: detector miss nhiều góc nghiêng
### Cách chặn
- benchmark sớm bằng chapter khó
- nếu miss nhiều thật, nâng detector sau benchmark
- không đoán bù bằng LLM trên đường chính

---

## Rủi ro 2: merge nhầm 2 nhân vật giống nhau
### Cách chặn
- conservative threshold
- anchor-first
- yellow zone review
- unknown-first policy

---

## Rủi ro 3: UI review thành quá nặng
### Cách chặn
- chỉ bắt user review cluster cờ vàng / đỏ
- không bắt duyệt từng panel
- có panel inspector nhưng không ép dùng mọi lúc

---

## Rủi ro 4: cache sai làm dữ liệu cũ bám dai
### Cách chặn
- mọi cache phải gắn version
- detector_version
- embedder_version
- cluster_version
- chapter_content_hash

---

## 20. Những gì cố tình không làm ngay

Để giữ đúng sweet spot, các mục sau sẽ không được build ở vòng đầu:

- body detector phức tạp nhiều lớp
- vision LLM fallback tự động cho mọi case
- multi-detector ensemble
- cross-chapter auto matching ngay từ đầu
- relationship graph
- scene-level identity reasoning
- perfect handling cho silhouette-only panel

Lý do rất đơn giản: những thứ này làm dự án phình ra và kéo tốc độ xuống trước khi lõi chính kịp ổn định.

---

## 21. Kết luận cuối cùng

Hướng final nên build cho manga-recap-tool là:

**một Character Prepass bảo thủ, nhẹ, có UI review ngắn, và khóa tên bằng data mapping trước khi đi vào Script.**

Pipeline chốt:

1. detect face/head  
2. quality gate  
3. embedding  
4. agglomerative clustering  
5. build character cards  
6. user rename / lock / merge / unknown  
7. export panel_character_refs  
8. Script step bắt buộc dùng canonical names

Đây là điểm ngọt tốt nhất vì nó:

- giải đúng vấn đề tên gọi không nhất quán,
- ít dữ liệu bẩn hơn cách prompt-only,
- nhanh hơn rất nhiều so với vision LLM pipeline,
- dễ debug,
- dễ cache,
- dễ mở rộng sang cross-chapter memory về sau.

---

## 22. Quyết định cuối cùng cần khóa

Để tránh drift kỹ thuật, hệ Character ở giai đoạn đầu phải khóa các quyết định sau:

- **1 detector**
- **1 embedding model**
- **1 clustering mặc định là Agglomerative**
- **unknown-first**
- **split-over-merge**
- **canonical name lock**
- **không vision LLM trên đường chính**
- **không re-run khi chỉ đổi tên**
- **Character step nằm giữa Extract và Script**

Đây là bộ nguyên tắc đủ chặt để triển khai thực tế mà không bị trôi thành một nhánh nghiên cứu quá dài.
