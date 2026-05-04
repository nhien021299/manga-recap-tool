import io
import re
import numpy as np
import soundfile as sf


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

def merge_dialogue_into_narration(narration: str, dialogue: str | None, speaker: str | None = None) -> str:
    if not dialogue:
        return narration

    n = narration.strip()
    if n and n[-1] not in ".!?":
        n += "."

    d = dialogue.strip()
    word_count = count_words(d)
    name = speaker.strip() if speaker else "Hắn"

    return f"{n} {name} nói. ...{d}"

def split_into_tts_chunks(text: str, min_words=6, ideal_max=18, hard_max=26) -> list[str]:
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

    # Split chunks that exceed ideal_max by comma, colon, or semicolon.
    final = []
    for chunk in merged:
        if count_words(chunk) <= ideal_max:
            final.append(chunk)
            continue

        # Try splitting by comma, colon, semicolon
        parts = re.split(r"(?<=[,;:])\s+", chunk)
        if len(parts) <= 1:
            # No split points found, keep as-is
            final.append(chunk)
            continue

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

def concatenate_and_pad_audio(
    wav_chunks: list[bytes], 
    start_pad_ms: int = 150, 
    end_pad_ms: int = 600, 
    internal_pause_ms: int = 200,
    target_sr: int = 24000
) -> bytes:
    """Concatenate multiple wav files (as bytes) into a single wav (bytes), with silence padding."""
    if not wav_chunks:
        # Return just silence if no chunks
        silence_samples = int(target_sr * (start_pad_ms + end_pad_ms) / 1000.0)
        silence = np.zeros(silence_samples, dtype=np.float32)
        out_io = io.BytesIO()
        sf.write(out_io, silence, target_sr, format="WAV")
        return out_io.getvalue()

    arrays = []
    sr = target_sr
    
    # Read all chunks
    for w in wav_chunks:
        data, current_sr = sf.read(io.BytesIO(w))
        if current_sr != sr:
            # We assume constant sample rate or minimal processing required.
            # VieNeu typically returns 24kHz. Let's just update the target to current if it's the first one,
            # or ignore resampling complexity since VieNeu is fixed.
            sr = current_sr
        if len(data.shape) > 1:
            data = data.mean(axis=1) # convert to mono just in case
        arrays.append(data.astype(np.float32))

    # Create silences
    start_pad = np.zeros(int(sr * start_pad_ms / 1000.0), dtype=np.float32)
    end_pad = np.zeros(int(sr * end_pad_ms / 1000.0), dtype=np.float32)
    internal_pause = np.zeros(int(sr * internal_pause_ms / 1000.0), dtype=np.float32)

    # Interleave
    final_parts = [start_pad]
    for i, arr in enumerate(arrays):
        final_parts.append(arr)
        if i < len(arrays) - 1:
            final_parts.append(internal_pause)
    final_parts.append(end_pad)

    final_audio = np.concatenate(final_parts)

    out_io = io.BytesIO()
    sf.write(out_io, final_audio, sr, format="WAV")
    return out_io.getvalue()
