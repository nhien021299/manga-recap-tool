# OCR + Vision Rollout Plan for Qwen Models

## Mục tiêu

Tài liệu này chốt kế hoạch triển khai luồng **OCR + Vision** cho backend FastAPI hiện tại, với mục tiêu cải thiện chất lượng caption/understanding của manga panels trước khi đổ sang bước gen script.

Tài liệu cũng cập nhật lại **kịch bản test và chấm điểm** cho 3 model:
- `qwen3-vl:4b`
- `qwen2.5vl:7b`
- `gemma3:latest`

Theo 2 trạng thái:
- **Before OCR**: vision-only
- **After OCR**: OCR + vision merge

---

## 1. Bối cảnh hiện tại

Theo trạng thái M2 hiện tại của repo:
- frontend/backend local flow đã chạy end-to-end ổn
- timeout/retry/runtime đã được harden đủ để chạy chapter thật
- bottleneck chính nằm ở **caption / vision quality**, không còn nằm ở queue, polling hay runtime path nữa
- visual-only prompt giúp giảm lore leakage, nhưng caption vẫn còn quá generic trên chapter test 52 panels
- roadmap đã xác định: nếu vision-only model mạnh hơn vẫn chưa đạt, hướng tiếp theo là **OCR-aware caption path**

Ý nghĩa thực dụng:
- không nên tiếp tục vặn timeout hoặc prompt nhỏ lẻ như hướng chính
- nên thêm **một tín hiệu grounding mới** vào pipeline, và tín hiệu đó là OCR

---

## 2. Vấn đề cần giải quyết

### 2.1 Lỗi điển hình của vision-only
Với manga panel, model vision thường gặp 5 lỗi lớn:

1. **Over-interpretation**
   - ánh sáng, motion line, silhouette bị hiểu thành thực thể hoặc sự kiện sai
   - ví dụ: tia sét bị diễn giải thành “hình dạng ma quái”

2. **Generic caption**
   - mô tả kiểu “một người đang đứng”, “khung cảnh u ám”, “có chuyện xảy ra”

3. **Miss text / SFX**
   - bỏ sót chữ tượng thanh hoặc không tận dụng text hiện diện trong panel

4. **Miss panel structure**
   - không tách main panel và inset panel

5. **Weak script grounding**
   - caption sai hoặc mơ hồ dẫn đến script hợp lệ về schema nhưng yếu về nội dung

### 2.2 Vì sao OCR giúp
OCR cung cấp **text thật** từ panel:
- speech bubble
- caption box
- SFX
- chữ trên bảng, giấy, vũ khí, vật thể

Text này đóng vai trò **anchor** cho vision:
- vision nói “ánh sáng trắng mạnh, vệt kéo dài”
- OCR nói “thunder / boom / 雷 / 轰”
- merge lại sẽ nghiêng về “tia sét / va đập” thay vì “ma quái”

OCR không thay vision, mà **ghim nghĩa** cho vision.

---

## 3. Kiến trúc mục tiêu

### 3.1 Luồng hiện tại

```text
image -> qwen vision -> understandings -> script generation
```

### 3.2 Luồng mới đề xuất

```text
image
  -> preprocess
  -> OCR adapter
  -> Qwen vision caption
  -> merge layer (rule-based + light LLM normalization)
  -> grounded understandings
  -> script generation
```

### 3.3 Triết lý triển khai
- giữ nguyên backend contract đang chạy được nếu có thể
- thêm OCR như một lớp độc lập, không phá flow cũ
- cho phép bật/tắt bằng config
- benchmark được **before / after OCR** trên cùng chapter, cùng model, cùng chunk size

---

## 4. Đề xuất module trong backend

### 4.1 Provider adapters
Tạo thêm abstraction mới trong `ai-backend`:

```text
app/
  providers/
    ocr/
      base.py
      local_ocr.py
```

Interface gợi ý:

```python
class OCRProvider(Protocol):
    async def extract(self, image_path: str) -> OCRResult:
        ...
```

### 4.2 Data models

#### OCRResult
```json
{
  "panel_id": "scene-001.png",
  "lines": [
    {
      "text": "轰",
      "confidence": 0.91,
      "role": "sfx",
      "bbox": [10, 20, 200, 330]
    }
  ],
  "full_text": "轰",
  "has_text": true
}
```

#### VisionCaptionRaw
```json
{
  "panel_id": "scene-001.png",
  "main_event": "Bright branching light cuts through heavy rain above a rooftop.",
  "inset_event": "A basket or container is knocked over and leaves spill out.",
  "visible_objects": ["lightning", "rain", "rooftop edge", "basket", "leaves"],
  "visible_text": [],
  "sfx_guess": ["unreadable stylized sound effect"],
  "scene_tone": "sudden, violent, tense"
}
```

#### GroundedUnderstanding
```json
{
  "panelId": "scene-001.png",
  "orderIndex": 0,
  "summary": "Một tia sét lớn xé ngang bầu trời trong mưa, chiếu sáng mép mái nhà. Ở khung phụ, một vật chứa bị lật làm lá văng ra ngoài.",
  "action": "Tia sét giáng xuống trong mưa; đồng thời một vật chứa trong khung phụ bị xô đổ.",
  "emotion": "Căng thẳng, đột ngột",
  "dialogue": "",
  "sfx": ["thunder crash"],
  "cliffhanger": "Cú sét dữ dội và vật thể bị lật đổ báo hiệu một biến cố vừa xảy ra."
}
```

---

## 5. Schema nên đổi thế nào

Schema hiện tại hơi khuyến khích model “kể chuyện sớm”.

### 5.1 Schema cũ
```json
{
  "summary": "",
  "action": "",
  "emotion": "",
  "dialogue": "",
  "sfx": [],
  "cliffhanger": ""
}
```

### 5.2 Schema mới khuyến nghị

#### Layer A: visual facts
```json
{
  "main_event": "",
  "inset_event": "",
  "visible_objects": [],
  "visible_text": [],
  "sfx_guess": [],
  "scene_tone": ""
}
```

#### Layer B: grounded understanding
```json
{
  "summary": "",
  "action": "",
  "emotion": "",
  "dialogue": "",
  "sfx": [],
  "cliffhanger": ""
}
```

### 5.3 Lợi ích
- layer A buộc model nhìn đúng trước
- layer B mới cho phép diễn giải nhẹ
- merge layer có thể dùng OCR để sửa layer A trước khi đẩy sang layer B

---

## 6. Prompt chiến lược cho Qwen vision

### 6.1 Prompt cũ cần tránh
- cho phép model infer identity
- cho phép gọi tên quái vật/ma/quái lực khi không có đủ chứng cứ
- không bắt tách main panel và inset panel

### 6.2 Prompt vision v2

```text
Describe only what is directly visible in the manga panel.

Rules:
- Do NOT infer ghost, monster, identity, or story meaning unless clearly shown.
- If there is an inset panel, separate the main panel event and inset panel event.
- Prefer physical descriptions over interpretation.
- Describe exact visible actions using concrete verbs.
- If text is readable, extract it exactly.
- If text is stylized or unclear, mark it as SFX or unreadable text.
- If no face is visible, describe scene tension instead of character emotion.

Return JSON with:
- main_event
- inset_event
- visible_objects
- visible_text
- sfx_guess
- scene_tone
```

### 6.3 Prompt merge v1
Dùng cho bước hợp nhất OCR + vision:

```text
You are merging OCR output with visual facts from a manga panel.

Goals:
- keep the result grounded in what is directly visible
- use OCR text to clarify sound effects, labels, speech, and captions
- do not invent identities or story lore
- if OCR strongly indicates thunder, impact, or attack SFX, prefer that interpretation over supernatural guesses
- keep summary concise but specific

Return JSON with:
- summary
- action
- emotion
- dialogue
- sfx
- cliffhanger
```

---

## 7. Kế hoạch triển khai theo phase

## Phase 0. Giữ baseline để đối chiếu
Trước khi thêm OCR:
- đóng băng config hiện tại của vision-only path
- giữ chapter test 52 panels làm benchmark chuẩn
- chốt 3 model benchmark ban đầu:
  - `qwen3-vl:4b`
  - `qwen2.5vl:7b`
  - `gemma3:latest`

Mục tiêu:
- có baseline “before OCR” thật sạch để so với “after OCR”

---

## Phase 1. Thêm OCR adapter
Yêu cầu kỹ thuật:
- OCR adapter chạy local
- trả ra text lines + confidence + bbox nếu có
- có config bật/tắt bằng `.env`

Biến config gợi ý:

```env
AI_BACKEND_OCR_ENABLED=true
AI_BACKEND_OCR_MIN_CONFIDENCE=0.55
AI_BACKEND_OCR_MAX_TEXT_LINES=20
AI_BACKEND_OCR_PREFER_SFX=true
AI_BACKEND_OCR_DEBUG_SAVE_JSON=true
```

Deliverables:
- provider abstraction
- response model
- unit test cho panel có text / không text

---

## Phase 2. Tách vision output thành visual facts
Thay vì để qwen đi thẳng vào `summary/action/emotion`, bắt qwen trả về:
- `main_event`
- `inset_event`
- `visible_objects`
- `visible_text`
- `sfx_guess`
- `scene_tone`

Mục tiêu:
- giảm không gian cho hallucination narrative
- dễ merge với OCR hơn

Deliverables:
- schema mới
- validation mới
- fallback path nếu model trả JSON lỗi

---

## Phase 3. Thêm merge layer
Merge layer nhận vào:
- OCRResult
- VisionCaptionRaw

Và tạo ra `GroundedUnderstanding`.

### 3.1 Rule-based trước, LLM sau
Khuyến nghị thứ tự:
1. rule-based normalization
2. qwen text hoặc merge prompt nhẹ nếu cần

### 3.2 Rule ưu tiên
- nếu OCR có text confidence cao và giống SFX/thunder/impact, ưu tiên map sang `sfx`
- nếu OCR có speech bubble text, ưu tiên đưa vào `dialogue`
- nếu vision nói về thực thể siêu nhiên nhưng OCR và visible_objects đều không support, hạ mức certainty
- nếu có inset_event rõ, bắt buộc nhắc đến trong summary hoặc action

Deliverables:
- `merge_caption_with_ocr()`
- regression tests cho case “lightning -> ghost”
- saved debug JSON cho từng panel

---

## Phase 4. Tích hợp vào script pipeline
Sau khi đã có `GroundedUnderstanding`:
- bước script generation không cần đổi kiến trúc lớn
- chỉ cần đổi input source từ `vision_only_understanding` sang `grounded_understanding`

Mục tiêu:
- giữ script stage càng ổn định càng tốt
- chứng minh rằng chất lượng script tăng lên nhờ input caption tốt hơn

Deliverables:
- giữ nguyên contract `generatedItems`
- thêm log field `caption_source=vision_only|vision_ocr`

---

## Phase 5. Telemetry và debug
Cần log thêm:
- `ocrMs`
- `visionMs`
- `mergeMs`
- `ocrHasText`
- `ocrLineCount`
- `mergeCorrectionTags`

Ví dụ correction tags:
- `sfx_grounded`
- `dialogue_grounded`
- `hallucination_dampened`
- `inset_recovered`

---

## 8. Kịch bản test mới: before vs after OCR

## 8.1 Mục tiêu benchmark mới
Không chỉ hỏi “model nào tốt hơn”, mà hỏi:

1. model nào tốt hơn ở vision-only?
2. model nào hưởng lợi nhiều hơn khi thêm OCR?
3. OCR có giúp model nhẹ (`qwen3-vl:4b`) bắt kịp một phần model nặng (`qwen2.5vl:7b`) hay không?
4. runtime tăng thêm có đáng đổi lấy chất lượng không?

---

## 8.2 Bộ test chính thức

### Dataset
- chapter chuẩn: `D:\Manhwa Recap\Tâm Ma\chapter 1 cropped`
- số panels: `52`

### Models
- `qwen3-vl:4b`
- `qwen2.5vl:7b`
- `gemma3:latest`

Ghi chú:
- `gemma3:latest` được thêm vào để làm **baseline đối chiếu** trước và sau OCR
- không mặc định xem đây là candidate production chính trừ khi benchmark thực tế đảo ngược kỳ vọng

### Modes
- `vision_only`
- `vision_ocr`

### Matrix test

| Test ID | Model | Mode |
|---|---|---|
| T1 | qwen3-vl:4b | vision_only |
| T2 | qwen2.5vl:7b | vision_only |
| T3 | gemma3:latest | vision_only |
| T4 | qwen3-vl:4b | vision_ocr |
| T5 | qwen2.5vl:7b | vision_ocr |
| T6 | gemma3:latest | vision_ocr |

---

## 8.3 Workloads
Mỗi test chạy 3 mức:
- 10 panels
- 30 panels
- 52 panels

Nếu 52 panels pass ổn thì mở rộng thêm:
- 60 panels
- 80 panels

---

## 8.4 Config cố định để so sánh công bằng

### Before OCR
```env
AI_BACKEND_CAPTION_CHUNK_SIZE=1
AI_BACKEND_CAPTION_MAX_TOKENS=512
AI_BACKEND_OCR_ENABLED=false
```

### After OCR
```env
AI_BACKEND_CAPTION_CHUNK_SIZE=1
AI_BACKEND_CAPTION_MAX_TOKENS=512
AI_BACKEND_OCR_ENABLED=true
```

Giữ nguyên các thông số khác như timeout, resize, retry.

---

## 9. Hệ thống chấm điểm mới

## 9.1 Runtime metrics
Ghi lại cho mỗi run:
- `totalMs`
- `captionMs`
- `ocrMs`
- `mergeMs`
- `scriptMs`
- `avgPanelMs`
- `p95PanelMs`

### Runtime target
| Workload | Target |
|---|---|
| 10 panels | < 25s |
| 30 panels | < 75s |
| 52 panels | càng gần 120s càng tốt |
| 60-80 panels warmed | mục tiêu dưới 2 phút nếu có thể |

---

## 9.2 Caption quality metrics
Mỗi panel chấm theo 1-5:

### A. Visual fidelity
Model có mô tả đúng thứ đang thấy không?
- 1 = sai bản chất hình
- 3 = đúng đại ý nhưng mơ hồ
- 5 = đúng và cụ thể

### B. Action clarity
Hành động chính có rõ không?
- ví dụ: “tia sét giáng xuống”, “vật chứa bị lật”, “nhân vật rút kiếm”

### C. Text/SFX grounding
- đọc text hoặc SFX đúng không?
- nếu không đọc được, có ít nhất gắn đúng kiểu `unreadable SFX` thay vì bịa không?

### D. Structure awareness
- có nhận ra inset panel không?
- có tách main event / inset event không?

### E. Script usefulness
- caption này có đủ dùng để bước script viết tiếp không?
- hay vẫn quá generic để tạo narration mạnh?

---

## 9.3 Error tags
Mỗi panel cho phép gắn nhiều lỗi:
- `hallucination_entity`
- `hallucination_story`
- `generic_caption`
- `miss_sfx`
- `miss_dialogue`
- `miss_inset`
- `wrong_action`
- `wrong_emotion`
- `usable_but_weak`

---

## 9.4 Weighted score

### Panel score
```text
panel_score =
  visual_fidelity * 0.30 +
  action_clarity * 0.20 +
  text_sfx_grounding * 0.20 +
  structure_awareness * 0.15 +
  script_usefulness * 0.15
```

### Run score
- lấy trung bình tất cả panel_score
- trừ penalty nếu error tags nặng xuất hiện nhiều

### Penalty gợi ý
- `hallucination_entity`: -0.40 mỗi lần
- `hallucination_story`: -0.30 mỗi lần
- `wrong_action`: -0.20 mỗi lần
- `generic_caption`: -0.10 mỗi lần
- `miss_inset`: -0.10 mỗi lần

---

## 9.5 Cách đọc kết quả

### Nếu `vision_ocr` tăng điểm mạnh
Kết luận:
- OCR đáng đầu tư
- model hiện tại vẫn dùng được nếu có grounding

### Nếu `qwen3-vl:4b + OCR` tiệm cận `qwen2.5vl:7b vision_only`
Kết luận:
- có thể dùng model nhẹ hơn cho production nếu latency là ưu tiên lớn

### Nếu `gemma3:latest + OCR` chỉ tăng nhẹ nhưng vẫn generic
Kết luận:
- giữ `gemma3:latest` làm baseline ổn định hoặc model debug
- không dùng làm production caption model chính

### Nếu `qwen2.5vl:7b + OCR` vượt rõ rệt nhưng vẫn trong runtime chấp nhận được
Kết luận:
- đây là candidate production tốt nhất

### Nếu cả 3 model sau OCR vẫn còn nhiều hallucination nặng
Kết luận:
- phải tăng sức nặng merge layer hoặc tách riêng OCR type-aware classification

---

## 10. Script benchmark mới

## 10.1 Vì sao phải test script lại
OCR + vision không chỉ thay caption.
Nó có thể thay trực tiếp chất lượng:
- `ai_view`
- `voiceover_text`
- `storyMemories`

Nên sau mỗi run caption benchmark, cần đẩy tiếp sang script generation cho ít nhất:
- 10 panels
- 30 panels
- full 52 panels

### Chỉ số script cần chấm
- hook strength
- continuity
- semantic faithfulness to panel
- repetition rate
- tension / pacing

### Mục tiêu
Script phải:
- bớt generic hơn baseline
- giảm câu “có điều gì đó đáng sợ đang xảy ra” kiểu rỗng
- tăng mô tả hành động cụ thể và quan hệ nhân quả

---

## 11. Quy tắc ra quyết định cuối

## Case A. Chọn `qwen2.5vl:7b + OCR`
Chọn khi:
- caption score cao nhất
- hallucination giảm rõ
- script cải thiện rõ
- runtime vẫn chịu được cho chapter thật

## Case B. Chọn `qwen3-vl:4b + OCR`
Chọn khi:
- caption score thấp hơn một ít nhưng latency tốt hơn nhiều
- script sau OCR vẫn đủ dùng cho production
- chapter lớn cần throughput cao hơn

## Case C. Giữ `gemma3:latest` làm baseline
Chọn khi:
- cần một mốc đối chiếu ổn định để kiểm tra regression
- muốn xác nhận lợi ích thật của OCR bằng cách so với model cũ
- không đặt kỳ vọng đây là model production cuối

## Case D. Hybrid
Chọn khi:
- `qwen3-vl:4b + OCR` đủ tốt cho đa số panel
- `qwen2.5vl:7b + OCR` chỉ cần cho panel khó

Pipeline hybrid:
```text
all panels -> qwen3-vl:4b + OCR
hard panels only -> qwen2.5vl:7b + OCR recheck
```

Hard panel criteria:
- nhiều SFX lớn
- nhiều inset
- motion quá dày
- OCR có text nhưng vision confidence thấp
- merge layer gắn tag `hallucination_dampened`

---

## 12. Deliverables đề xuất

### Tài liệu
- file benchmark guide này
- prompt v2 cho vision
- prompt v1 cho merge

### Code
- OCR provider abstraction
- OCRResult schema
- VisionCaptionRaw schema
- merge layer
- benchmark script cập nhật mode before/after OCR

### Logs / outputs
- `captions_raw.jsonl`
- `ocr_raw.jsonl`
- `merged_understandings.jsonl`
- `auto_scores.csv`
- `manual_review.csv`
- `SUMMARY.md`

---

## 13. Kịch bản thực thi ngắn gọn

### Round 1. Baseline
- T1: qwen3-vl:4b vision_only
- T2: qwen2.5vl:7b vision_only
- T3: gemma3:latest vision_only

### Round 2. OCR integration
- bật OCR adapter
- chạy T4, T5, T6

### Round 3. Manual review
- chấm 10-15 panel tiêu biểu mỗi test
- bắt buộc có 3 nhóm panel:
  - action-heavy
  - text/SFX-heavy
  - dark/ambiguous panels

### Round 4. Script review
- đọc script output của 6 test
- so semantic faithfulness và pacing

### Round 5. Quyết định
- chọn 1 trong 4: qwen2.5+OCR, qwen3+OCR, gemma3 baseline-only, hybrid

---

## 14. Kết luận

Đối với trạng thái hiện tại của dự án, bước thêm **OCR + vision** không phải là “thêm tính năng cho vui”.
Nó là bước **grounding bắt buộc** nếu vision-only vẫn còn diễn giải quá đà, đặc biệt trên manga panels có:
- SFX stylized
- mưa, chớp, motion lines
- inset panels
- bố cục dày đặc

Mục tiêu của rollout này không phải biến Qwen thành model hoàn hảo.
Mục tiêu là:
- giảm hallucination
- tăng specificity
- tăng script usefulness
- giữ runtime đủ thực dụng cho chapter thật

Khi benchmark xong 6 test T1-T6, bạn sẽ có câu trả lời rõ ràng hơn nhiều:
- OCR có cứu được model nhẹ không
- model nặng có thật sự đáng tiền không
- `gemma3:latest` còn giữ được vai trò gì ngoài baseline
- production nên đi theo hướng single model hay hybrid

