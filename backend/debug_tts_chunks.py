"""Debug script: show exactly what text VieNeu TTS receives for each scene after chunking."""
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

from app.utils.tts_adapter import (
    merge_dialogue_into_narration,
    normalize_tts_text,
    split_into_tts_chunks,
    count_words,
)

def analyze_chapter(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"=== {data.get('project')} Chapter {data.get('chapter')} ===")
    print(f"Total scenes: {len(data['scenes'])}\n")

    problems = []

    for scene in data["scenes"]:
        num = scene["scene"]
        narration = scene.get("narration", "")
        dialogue = scene.get("dialogue")
        speaker = scene.get("dialogue_speaker")

        # Step 1: Merge
        raw = merge_dialogue_into_narration(narration, dialogue, speaker)
        # Step 2: Normalize
        normalized = normalize_tts_text(raw)
        # Step 3: Chunk
        chunks = split_into_tts_chunks(normalized)

        total_words = count_words(normalized)
        print(f"--- Scene {num:02d}: {scene.get('title', '')} ---")
        print(f"  Normalized ({total_words}w): {normalized}")
        print(f"  Chunks ({len(chunks)}):")
        for i, c in enumerate(chunks, 1):
            wc = count_words(c)
            flag = " ⚠️ LONG" if wc > 18 else ""
            print(f"    [{i}] ({wc}w){flag}: {c}")
        print()

        # Flag problems
        for i, c in enumerate(chunks, 1):
            wc = count_words(c)
            if wc > 18:
                problems.append((num, i, wc, c))

    if problems:
        print("=" * 60)
        print(f"⚠️  PROBLEMS: {len(problems)} chunks exceed 18 words")
        for scene_num, chunk_idx, wc, text in problems:
            print(f"  Scene {scene_num:02d} chunk {chunk_idx} ({wc}w): {text}")
    else:
        print("✅ All chunks are within 18-word limit!")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else r"D:\AI\Resources\chapter_2\chapter_2_narration_tts.json"
    analyze_chapter(path)
