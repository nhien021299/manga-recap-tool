# TTS Narration Stabilization Plan

## 0. Context

Project: Cau Ma  
Chapter: 2  
Language: Vietnamese / vi-VN  
Target TTS model: VieNeuTTS standard or medium model, not turbo.

Current issue:
- Generated TTS sometimes has light echo/reverb.
- Some sentence endings are cut off.
- Some lines are not spoken fully.
- Short dialogue lines can sound unstable or get skipped.
- Narration JSON contains `duration_seconds`, but many durations are too short for the amount of text.

Core principle:

> Audio duration must drive scene duration. Do not force TTS audio to fit the original `duration_seconds`.

---

## 1. Main Diagnosis

The current narration JSON is good for story pacing, but not yet TTS-friendly.

Main causes:

1. **Text is too dense for the assigned duration**
   - Many scenes contain 30-55 Vietnamese words but are assigned only 3-6 seconds.
   - This causes TTS to rush, swallow words, distort prosody, or cut endings.

2. **Dialogue lines are too short**
   - Examples like `Ủa?`, `Về nhà!`, `Lạp Tô!` are risky when generated as isolated TTS clips.
   - VieNeuTTS-like local models are often unstable with very short segments.

3. **Audio is probably trimmed too close**
   - If the pipeline trims audio to `duration_seconds`, the final syllables can be cut.
   - Even if the model generated the full sentence, the export/merge step can remove the tail.

4. **Missing silence padding**
   - TTS clips need small silence buffers at the beginning and especially the end.
   - Without tail padding, the video/audio mux step may cut the last phoneme.

5. **Text normalization is not optimized**
   - Overuse of `!`, `...`, or very long clauses can increase instability.
   - Fantasy terms like `Hỏa Man lực`, `Man Khải`, `Khai Trần cảnh`, `Ô Long Tiên` should be preserved but rhythmically separated.

---

## 2. Target Behavior

The agent must convert the original script JSON into a TTS-safe runtime structure.

Original JSON fields:

```json
{
  "narration": "...",
  "duration_seconds": 5,
  "dialogue": "..."
}
```

Runtime TTS structure should become:

```json
{
  "scene": 1,
  "title": "...",
  "tts_chunks": [
    "Chunk 1.",
    "Chunk 2."
  ],
  "min_duration_seconds": 5,
  "actual_audio_duration_seconds": "auto_after_tts",
  "final_scene_duration_seconds": "max(min_duration_seconds, actual_audio_duration_seconds + 0.4)"
}
```

Important:
- `duration_seconds` becomes `min_duration_seconds`.
- It must not be used to hard-trim TTS.
- Final scene duration should follow actual generated audio length.

---

## 3. TTS-Friendly Text Rules

### 3.1 Chunk Length

Each TTS chunk should be:

```text
Ideal: 12-28 Vietnamese words
Acceptable: 8-35 Vietnamese words
Avoid: under 5 words
Avoid: over 40 words
```

### 3.2 Dialogue Handling

Do not generate ultra-short dialogue as standalone audio.

Bad:

```json
"dialogue": "Ủa?"
```

Good:

```text
Tô Minh khựng lại, bật ra một tiếng: Ủa?
```

Bad:

```json
"dialogue": "Về nhà!"
```

Good:

```text
Hắn siết lại chiếc sọt sau lưng, rồi nói khẽ: Về nhà.
```

Bad:

```json
"dialogue": "Lạp Tô!"
```

Good:

```text
Từ phía trong bộ lạc, có người bật gọi lớn: Lạp Tô.
```

### 3.3 Punctuation Rules

Before sending text to TTS:

- Replace `...` and `…` with `.`
- Prefer `.` over `!` for narration.
- Keep `?` only when needed.
- Avoid multiple punctuation marks.
- Ensure every chunk ends with `.`, `?`, or `!`.
- Add natural pause by splitting long sentences instead of using too many commas.

### 3.4 Fantasy Term Handling

Preserve these terms exactly:

```text
Tô Minh
A Công
Ô Sơn
Ô Long Tiên
Hỏa Man
Hỏa Man lực
Man Khải
Man thể
Man Sĩ
Man Văn
Man Huyết
Khai Trần
Khai Trần cảnh
Phong Quyến
Sơn Ngân
Lạp Tô
```

If pronunciation sounds unstable, add rhythm around the term by splitting the sentence. Do not rewrite names unless explicitly required.

---

## 4. Duration Rules

### 4.1 Estimated Duration

Use this formula for planning:

```python
estimated_duration = word_count / 3.2 + 0.5
```

Where:
- `3.2 words/second` is a fast but still understandable Vietnamese recap pace.
- `+0.5` gives breathing room.

### 4.2 Scene Duration

After TTS generation:

```python
final_scene_duration = max(min_duration_seconds, actual_audio_duration + 0.4)
```

Never do this:

```python
final_audio = trim(audio, duration_seconds)
```

### 4.3 Speed Adjustment

Allowed:
- Slow down or keep natural.
- Speed-up only if absolutely needed.

Limits:

```text
Safe speed-up: 1.00x - 1.05x
Risky: 1.06x - 1.10x
Avoid: above 1.10x
```

If audio is too long, prefer trimming text, not speeding up too much.

---

## 5. Audio Padding Rules

Every TTS clip must receive silence padding.

Recommended:

```text
Start padding: 100-200 ms
End padding: 500-700 ms
```

Minimum:

```text
End padding: 400 ms
```

FFmpeg simple version:

```cmd
ffmpeg -i input.wav -af "apad=pad_dur=0.6" -ar 24000 -ac 1 output_padded.wav
```

Safer version with leading and ending silence can be done inside Python or audio library.

Do not aggressively remove silence after TTS generation. If silence removal is used, it must not remove the final tail.

---

## 6. Audio Export Rules

Recommended output format:

```text
Sample rate: 24000 Hz
Channel: mono
Format: wav
Bit depth: default PCM is acceptable
```

Avoid unnecessary post-processing.

Use this first:

```cmd
ffmpeg -i input.wav -af "apad=pad_dur=0.6" -ar 24000 -ac 1 output.wav
```

Only use loudness normalization if volume is inconsistent:

```cmd
ffmpeg -i input.wav -af "apad=pad_dur=0.6,loudnorm=I=-16:TP=-1.5:LRA=11" -ar 24000 -ac 1 output.wav
```

If `loudnorm` creates pumping, echo, or metallic sound, remove it.

Avoid these unless tested carefully:
- heavy denoise
- aggressive compression
- reverb
- stereo widening
- strong EQ
- forced silence trimming

---

## 7. Agent Pipeline

The agent should execute the following steps.

### Step 1: Load JSON

Read the chapter JSON.

For each scene:
- scene number
- title
- narration
- dialogue
- duration_seconds

### Step 2: Build Raw TTS Text

If `dialogue` is null:

```text
raw_tts_text = narration
```

If `dialogue` exists:
- Merge dialogue naturally into narration.
- Do not generate dialogue as a separate tiny clip unless dialogue has enough words.

Example:

```text
raw_tts_text = narration + " " + dialogue_contextualized
```

### Step 3: Normalize Text

Apply text normalization:
- Replace `…` and `...`
- Clean repeated spaces
- Normalize punctuation
- Ensure sentence endings
- Preserve glossary terms

### Step 4: Split Into Chunks

Split by sentence first.

Then:
- Merge tiny chunks under 5 words with adjacent chunk.
- Split chunks over 35-40 words at commas or natural phrase boundaries.
- Keep each chunk ideally 12-28 words.

### Step 5: Estimate Duration

For each scene:
- Count words from all chunks.
- Estimate duration with:

```python
estimated_duration = word_count / 3.2 + 0.5
```

Store:

```json
"estimated_tts_duration_seconds": estimated_duration
```

### Step 6: Generate TTS Per Chunk

Generate TTS chunk by chunk.

Recommended:
- One wav per chunk.
- Concatenate chunks with short internal pause.

Internal pause between chunks:

```text
150-250 ms
```

### Step 7: Concatenate Scene Audio

For each scene:
- Join chunk wavs.
- Add 100-200 ms silence at start.
- Add 500-700 ms silence at end.
- Export scene wav.

### Step 8: Measure Actual Audio Duration

After export:
- Measure final wav duration.
- Store:

```json
"actual_audio_duration_seconds": actual_duration
```

### Step 9: Set Final Scene Duration

Calculate:

```python
final_scene_duration = max(original_duration_seconds, actual_audio_duration_seconds + 0.4)
```

Store:

```json
"final_scene_duration_seconds": final_scene_duration
```

### Step 10: Render Video Using Final Duration

Video/image duration must follow:

```text
final_scene_duration_seconds
```

Not the original `duration_seconds`.

---

## 8. Pseudocode

```python
def prepare_scene_for_tts(scene):
    narration = scene.get("narration") or ""
    dialogue = scene.get("dialogue")

    raw_text = merge_dialogue_into_narration(narration, dialogue)
    normalized = normalize_tts_text(raw_text)
    chunks = split_into_tts_chunks(normalized)

    word_count = count_words(" ".join(chunks))
    estimated_duration = word_count / 3.2 + 0.5

    return {
        "scene": scene["scene"],
        "title": scene["title"],
        "tts_chunks": chunks,
        "min_duration_seconds": scene.get("duration_seconds", 0),
        "estimated_tts_duration_seconds": round(estimated_duration, 2)
    }


def finalize_scene_duration(scene_runtime, actual_audio_duration):
    return max(
        scene_runtime["min_duration_seconds"],
        actual_audio_duration + 0.4
    )
```

---

## 9. Reference Python Helpers

```python
import re

GLOSSARY = [
    "Tô Minh",
    "A Công",
    "Ô Sơn",
    "Ô Long Tiên",
    "Hỏa Man",
    "Hỏa Man lực",
    "Man Khải",
    "Man thể",
    "Man Sĩ",
    "Man Văn",
    "Man Huyết",
    "Khai Trần",
    "Khai Trần cảnh",
    "Phong Quyến",
    "Sơn Ngân",
    "Lạp Tô",
]

def normalize_tts_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("…", ".")
    text = text.replace("...", ".")
    text = text.replace("!", ".")
    text = re.sub(r"([,.?])\s*", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if text and text[-1] not in ".?!":
        text += "."

    return text


def count_words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def merge_dialogue_into_narration(narration: str, dialogue: str | None) -> str:
    if not dialogue:
        return narration

    d = dialogue.strip()
    word_count = count_words(d)

    if word_count <= 4:
        return f"{narration} Hắn khẽ bật ra: {d}"

    return f"{narration} Hắn nói: {d}"


def split_into_tts_chunks(text: str, min_words=8, ideal_max=28, hard_max=38):
    # Basic sentence split.
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current = ""

    for sentence in sentences:
        candidate = (current + " " + sentence).strip() if current else sentence

        if count_words(candidate) <= ideal_max:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    # Merge tiny chunks.
    merged = []
    for chunk in chunks:
        if merged and count_words(chunk) < min_words:
            merged[-1] = f"{merged[-1]} {chunk}"
        else:
            merged.append(chunk)

    # Split very long chunks by comma if possible.
    final = []
    for chunk in merged:
        if count_words(chunk) <= hard_max:
            final.append(chunk)
            continue

        parts = re.split(r"(?<=,)\s+", chunk)
        buffer = ""

        for part in parts:
            candidate = (buffer + " " + part).strip() if buffer else part
            if count_words(candidate) <= ideal_max:
                buffer = candidate
            else:
                if buffer:
                    final.append(buffer)
                buffer = part

        if buffer:
            final.append(buffer)

    return final
```

---

## 10. Scene Quality Rules For Current Chapter

The following scenes are high-risk and should be automatically checked:

```text
Scene 7: narration + long dialogue, duration too short
Scene 8: duration only 3 seconds
Scene 15: long emotional line with ellipsis-like rhythm
Scene 17: fantasy terms + long sentence
Scene 18: narration + command dialogue, duration short
Scene 20: long narration + dialogue
Scene 23: long narration + important dialogue
Scene 24: emotional final scene, should not be rushed
```

For these scenes:
- Do not force 3-5 second timing.
- Let final duration follow generated audio.
- Add tail padding.
- Avoid splitting into tiny dialogue-only clips.

---

## 11. Acceptance Criteria

A scene passes if:

```text
No final syllable is cut.
No sentence is skipped.
No dialogue under 5 words is generated standalone.
No TTS chunk exceeds 40 words.
Final audio has at least 0.5s tail padding.
Scene video duration is >= actual audio duration + 0.4s.
Speech speed does not exceed 1.05x unless manually approved.
```

A full chapter passes if:

```text
95%+ of scenes have complete spoken text.
No more than 1 minor pronunciation issue per 10 scenes.
No obvious echo introduced by post-processing.
No abrupt audio cut at scene transitions.
Narration remains understandable at normal playback speed.
```

---

## 12. Implementation Priority

Implement in this order:

1. Stop trimming TTS audio by `duration_seconds`.
2. Add 0.6s tail padding to every scene wav.
3. Merge short dialogue into narration.
4. Add chunking logic.
5. Calculate final scene duration from actual audio duration.
6. Add logging for word count, estimated duration, actual duration, and final duration.
7. Add high-risk scene warnings.
8. Only then tune voice/reference/model settings.

---

## 13. Logging Format

For each scene, print:

```text
[Scene 07] words=55 | min=4.0s | estimated=17.7s | actual=16.9s | final=17.3s | chunks=3 | status=OK
```

Warnings:

```text
[WARN] Scene 07 original duration too short for text density.
[WARN] Scene 07 dialogue was merged because it has fewer than 5 words.
[WARN] Scene 18 contains fantasy terms, check pronunciation.
```

---

## 14. Final Rule

The agent must treat the original JSON as **story script**, not as final TTS timing.

The corrected flow is:

```text
Story JSON
-> TTS-friendly adapter
-> normalized chunks
-> TTS generation
-> audio padding
-> actual duration measurement
-> video timing update
-> final render
```

Do not let visual timing cut the voice.

Audio is the spine. Video follows the spine.
