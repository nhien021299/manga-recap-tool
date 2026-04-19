# Re-Plan: Character System for Direct Image-to-Script Flow (Optimized for Ollama)

## Core Constraint

This plan is built around the current real pipeline:

```text
image(s) -> prompt -> local AI -> full voiceover
```

Important constraints:
- No intermediate LLM step such as `image -> structured JSON -> script`.
- The LLM call should stay focused on producing **final voiceover directly**.
- Character system must support this direct generation flow.
- Priority is:
  1. speed,
  2. low input/output token usage,
  3. stable local inference,
  4. preserving narration quality.

This means the Character System should behave as a **lightweight prompt-support layer**, not a heavy reasoning layer.

---

## What Must Change

The old direction was too architecture-heavy:
- resolver
- scene context builder
- multiple structured layers
- optional memory objects

That design is good for a bigger system, but for your current local setup it adds:
- more processing steps,
- more text to inject,
- more tokens,
- more latency.

For your current goal, the Character System should instead be:

```text
small context memory + lightweight character hints + strict prompt rules
```

Not:
```text
full structured character understanding pipeline
```

---

## New Target

Build a **Minimal Character-Aware Prompt System** that:
- keeps naming consistent,
- avoids wrong names,
- does not bloat prompt size,
- works with direct image-to-script generation,
- keeps output as final full voiceover.

---

## Design Principle

### Character System should do only 3 jobs

1. Decide whether a name is safe to use.
2. Provide only the minimum useful character hint to the prompt.
3. Keep continuity across adjacent panels/scenes without flooding context.

If a feature does not improve one of these three, it should be postponed.

---

## New Flow

```text
Panel Images
  -> optional local image preprocessing / OCR
  -> tiny context memory lookup
  -> character hint injection
  -> direct prompt build
  -> Ollama / local LLM
  -> full voiceover output
  -> short memory update
```

Key point:
- The AI still returns **voiceover directly**.
- Character handling exists only to guide the prompt with minimal overhead.

---

## Character System Scope (MVP)

### Keep
- manga title: optional
- recent known character names: optional
- previous context summary: very short
- naming confidence rule
- neutral fallback labels

### Remove for now
- full character registry UI
- complex resolver pipeline
- large structured scene context
- heavy multi-stage entity reasoning
- passing all possible character profiles every time

---

## Optimization-First Rules

## Rule 1: Never inject global character list
Do not send all known character names into every prompt.

Why:
- wastes tokens,
- slows local inference,
- increases wrong-name hallucination risk.

Instead:
- send only names that are likely relevant to the current image batch.

---

## Rule 2: Context must be compressed
Previous context must be extremely short.

Recommended size:
- 1 sentence,
- or maximum 30 to 50 words.

Bad:
- long summaries,
- re-feeding previous scripts,
- carrying multiple old scenes.

Good:
- one-line continuity hint.

Example:
- "Ngay trước đó, nhân vật chính vừa bị dồn vào thế bất lợi và không khí đang cực kỳ căng thẳng."

---

## Rule 3: Names are optional, not mandatory
Do not force the model to use a character name every time.

If uncertain:
- use neutral labels like:
  - nam nhân
  - người đàn ông
  - cô gái
  - bóng người
  - đối thủ
  - kẻ kia

This is better than assigning the wrong name.

---

## Rule 4: Only inject character hints when they add value
If the image batch clearly revolves around a known character, inject the name.
If not, skip character hinting completely.

This keeps prompts lean.

---

## Rule 5: Keep output bounded
Do not let the local model write long free-form monologues.

Set prompt expectation tightly:
- one voiceover per panel,
- or one compact voiceover block for the current batch,
- concise but dramatic,
- no intro/outro filler.

---

## Revised Architecture

## Layer 1: Tiny Story Memory
Purpose:
- maintain continuity cheaply.

Recommended type:

```ts
type TinyMemory = {
  previousSummary: string
  recentNames: string[]
}
```

Constraints:
- `previousSummary` max 1 sentence
- `recentNames` max 2 or 3 names

This is intentionally tiny.

---

## Layer 2: Character Hint Selector
Purpose:
- choose whether to include names in prompt.

Recommended type:

```ts
type CharacterHint = {
  namesToInject: string[]
  useNeutralFallback: boolean
}
```

Logic:
- If OCR / previous context strongly suggests a known character -> include 1 to 2 names max.
- If not strong enough -> inject no names and enable neutral fallback rule.

This is not a full resolver.
This is just a lightweight selector.

---

## Layer 3: Direct Prompt Builder
Purpose:
- produce one compact final prompt for the local model.

The prompt should include only:
- style instruction,
- optional manga title,
- tiny previous context,
- minimal naming rule,
- current image batch,
- output format rule.

No extra JSON explanation unless absolutely required.

---

## Recommended Prompt Structure

```text
Bạn là người viết lời dẫn recap truyện tranh cho YouTube theo phong cách cực cuốn, nhịp nhanh, căng, giàu drama.

Bối cảnh trước:
{previous_summary_if_any}

Gợi ý tên nhân vật có thể liên quan:
{1-2 names only if really useful}

Quy tắc gọi tên:
- Chỉ dùng tên nếu thật sự chắc chắn từ ngữ cảnh hoặc hội thoại.
- Nếu chưa chắc, dùng mô tả trung tính như nam nhân, cô gái, bóng người, đối thủ.

Yêu cầu:
- Viết tiếng Việt.
- Viết trực tiếp lời dẫn cuối cùng.
- Không viết intro kiểu chào khán giả.
- Không tự bịa thêm danh tính hay twist.
- Câu văn ngắn gọn, giàu nhịp, giàu lực kéo.
- Giữ mạch nối với bối cảnh trước nếu ảnh hiện tại chưa cho thấy chuyển cảnh rõ ràng.
```

This is much lighter than a full structured prompt.

---

## Should Manga Title Be Included Every Time?

### Answer
Usually: no.

Use manga title only when:
- you process multiple different manga projects in parallel,
- you want project-level style separation,
- the title helps prevent confusion between sessions.

Otherwise:
- skip it to save tokens.

Recommended rule:
- store manga title in backend state,
- inject only when needed,
- do not hardcode it into every prompt by default.

---

## Should Main Character Name Be Included Every Time?

### Answer
No.

Use character names only when:
- the current image batch clearly centers on that character,
- OCR or continuity strongly supports the identity,
- the name improves clarity more than it costs tokens.

If the image is ambiguous:
- do not inject the main character name.

This directly reduces hallucination risk.

---

## Batch Strategy for Speed

### Goal
Reduce number of model calls without making each prompt too large.

### Recommended batching
- 2 to 4 related panels per call
- not entire chapter
- not single panel unless necessary

This balances:
- speed,
- context continuity,
- lower token overhead per panel.

### Why not bigger?
If you batch too many panels:
- input grows too much,
- inference slows,
- output becomes looser,
- naming drift gets worse.

---

## Memory Strategy for Speed

Do not store full prior narration.

Store only:
- one-line previous summary,
- max 2 or 3 recent names.

Example:

```ts
const tinyMemory = {
  previousSummary: "Không khí vừa bị đẩy lên đỉnh điểm khi đối thủ bất ngờ áp sát.",
  recentNames: ["A", "B"]
}
```

This is enough for local continuity without ballooning prompt size.

---

## Output Strategy for Quote Saving

Your token budget is affected by both input and output.

### To reduce input tokens
- remove redundant world-building text
- do not restate long manga summary every call
- keep memory to one sentence
- keep names to 1 or 2 max
- avoid giant schemas

### To reduce output tokens
- require concise voiceover
- set expected length clearly
- forbid intro/outro filler
- avoid asking for explanation or analysis

Recommended output guidance:
- 1 to 2 sentences per panel
- or 1 tight paragraph per small panel batch

---

## Practical MVP Plan

## Phase 1: Refactor Prompt Inputs
### Goal
Shrink the prompt to only the parts that matter.

### Tasks
- Remove fixed `mainCharacter` requirement.
- Make `mangaName` optional.
- Add `previousSummary` as one short sentence.
- Add optional `namesToInject` list with max 2 names.
- Add neutral fallback naming rule.
- Remove large descriptive overhead where possible.

### Done when
- The prompt becomes shorter.
- Output remains usable.
- The model stops overusing forced names.

---

## Phase 2: Add Tiny Memory
### Goal
Keep continuity with minimum token cost.

### Tasks
- After each generated voiceover, create a 1-line compressed summary.
- Keep max 2 or 3 recent names.
- Feed only this tiny memory into the next prompt.

### Done when
- Adjacent batches feel continuous.
- Prompt length stays stable.

---

## Phase 3: Add Character Hint Selector
### Goal
Inject names only when worth it.

### Inputs
- OCR text if available
- recentNames from memory
- optional manual known names
- image batch metadata if any

### Output
- `namesToInject`
- `useNeutralFallback`

### Tasks
- If strong signal -> inject name(s)
- If weak signal -> no names
- Cap names to 2

### Done when
- Wrong-name errors decrease.
- Prompt stays compact.

---

## Phase 4: Tune Batch Size
### Goal
Find the fastest stable direct-generation setup.

### Test matrix
- batch size 1
- batch size 2
- batch size 3
- batch size 4

Measure:
- latency,
- output quality,
- naming stability,
- token cost.

### Done when
- you choose one default batch size for production.

---

## Phase 5: Add Hard Output Constraints
### Goal
Prevent local model from wasting tokens.

### Tasks
- Ban intro phrases like:
  - chào mừng quay trở lại
  - trong tập trước
  - stay tuned
- Require direct narration only.
- Cap expected length.
- Keep sentence rhythm short for TTS.

### Done when
- voiceover becomes compact,
- no trailer-style filler remains.

---

## Prompt Template Recommendation (Optimized Version)

```text
Bạn là người viết lời dẫn recap truyện tranh cho YouTube theo phong cách cực cuốn, nhịp nhanh, căng và giàu drama.

{optional_previous_summary_block}

{optional_character_hint_block}

Quy tắc gọi tên:
- Chỉ dùng tên nếu thật sự chắc chắn từ ngữ cảnh hoặc hội thoại.
- Nếu chưa chắc, dùng mô tả trung tính như nam nhân, cô gái, bóng người, đối thủ.

Yêu cầu:
- Viết trực tiếp lời dẫn cuối cùng bằng tiếng Việt.
- Không chào mở đầu, không tóm tắt kiểu trailer, không nhắc tập trước theo kiểu YouTube.
- Không bịa thêm danh tính, động cơ hay twist nếu ảnh chưa cho thấy.
- Giữ mạch nối với ngữ cảnh trước nếu chưa có chuyển cảnh rõ.
- Câu văn gọn, giàu nhịp, giàu lực kéo, dễ nghe bằng TTS.
```

Note:
- Current image data is still provided to the model according to your chosen image path.
- This plan only changes how character context is injected.

---

## Final Recommendation

For your current stage, do not build a heavy character system.

Build a **speed-first minimal character system**:

- tiny memory,
- minimal name injection,
- strict uncertainty rule,
- neutral fallback labels,
- compact direct prompt.

That gives you:
- lower latency,
- lower token usage,
- better local stability,
- less hallucinated naming,
- no disruption to your direct image-to-script flow.

---

## Acceptance Criteria

This re-plan is successful when:
- the prompt is shorter than the current version,
- the model still returns full direct voiceover,
- continuity is preserved between adjacent batches,
- names are used more accurately,
- ambiguous scenes no longer force wrong names,
- local inference remains fast and stable.
