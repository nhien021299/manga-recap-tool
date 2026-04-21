"""Generate preview voice samples for every TTS preset via the backend API.

Usage (backend must be running on port 8000):
    python .bench/generate_all_samples.py

This generates one short WAV per voice preset, stored under
  .bench/samples/{provider}/{slug}.wav
so the static mount at /assets/voice-samples works correctly.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

import io as _io
sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000/api/v1"
OUTPUT_ROOT = Path(__file__).resolve().parent / "samples"
TIMEOUT = 600  # seconds per request

# ---------------------------------------------------------------------------
# Sample texts tuned for each narration style in manga recap.
# Short enough for quick preview (~5-8s), but stylistically representative.
# ---------------------------------------------------------------------------
SAMPLE_TEXTS: dict[str, str] = {
    # --- Vieneu presets ---
    # Nữ hook mở đầu (Bích Ngọc)
    "Bích Ngọc (Nữ - Miền Bắc)":
        "Nếu có một ngày bạn tỉnh dậy trong thân xác kẻ phản diện sắp bị giết ở chương một, bạn sẽ làm gì? "
        "Nhân vật chính của chúng ta đã chọn một cách mà không ai có thể ngờ tới.",

    # Nam dẫn plot (Phạm Tuyên)
    "Phạm Tuyên (Nam - Miền Bắc)":
        "Sau năm trăm năm bị phong ấn dưới đáy vực sâu, hắn cuối cùng cũng đã mở mắt nhìn lại thế gian. "
        "Không còn ai nhớ đến tên hắn, nhưng lần này, hắn sẽ khiến cả lục địa phải run rẩy.",

    # Nữ kể cảm xúc (Thục Đoan)
    "Thục Đoan (Nữ - Miền Nam)":
        "Cô ấy lặng lẽ nhìn bầu trời đầy sao, nơi người đó từng hứa sẽ quay về. "
        "Những cánh hoa rơi chậm rãi, như chính khoảng thời gian tươi đẹp mà họ đã vĩnh viễn đánh mất.",

    # Nam cao trào (Xuân Vĩnh)
    "Xuân Vĩnh (Nam - Miền Nam)":
        "Một cú chém xé toạc không gian! Máu đỏ nhuộm cả một vùng trời, "
        "và cuối cùng, gã Ma Vương tàn bạo nhất lịch sử cũng đã phải quỳ gối trước một con người.",

    # --- F5 presets ---
    "nu_review_cuon":
        "Các bạn ơi, bộ này thực sự quá đỉnh! Mới chương đầu mà twist liên tục, "
        "main bị phản bội rồi thức tỉnh sức mạnh ẩn giấu. Càng xem càng cuốn không dứt ra được luôn!",

    "nam_review_luc":
        "Tóm lại cho nhanh, nhân vật chính bị đuổi khỏi gia tộc vì bị coi là phế vật. "
        "Nhưng hắn không biết rằng, trong cơ thể mình đang ẩn chứa một bí mật mà cả thế giới đang thèm khát.",

    "nu_ke_chuyen_sau":
        "Cô ấy đã hy sinh tất cả, kể cả linh hồn mình để bảo vệ người mình yêu nhất. "
        "Nhưng khi sự thật tàn khốc được hé lộ, mọi thứ xung quanh dường như sụp đổ hoàn toàn.",

    "nam_cao_trao_gat":
        "Hắn bước ra từ đống đổ nát với ánh mắt lạnh lẽo đến thấu xương. "
        "Cả quân đoàn vạn người đồng loạt run rẩy. Trận chiến sinh tử thực sự giờ mới chính thức bắt đầu!",
}



def post_voice_generate(text: str, provider: str, voice_key: str, speed: float = 1.0) -> bytes:
    payload = json.dumps({
        "text": text,
        "provider": provider,
        "voiceKey": voice_key,
        "speed": speed,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/voice/generate",
        data=payload,
        headers={"Accept": "audio/wav", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def wav_info(path: Path) -> tuple[float, int]:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate() or 1), wf.getframerate()


def main() -> int:
    # Map from voice_key -> (provider, output_filename)
    jobs: list[dict] = [
        # Vieneu
        {"provider": "vieneu", "voiceKey": "Bích Ngọc (Nữ - Miền Bắc)",  "filename": "nu-hook-mo-dau.wav"},
        {"provider": "vieneu", "voiceKey": "Phạm Tuyên (Nam - Miền Bắc)", "filename": "nam-dan-plot.wav"},
        {"provider": "vieneu", "voiceKey": "Thục Đoan (Nữ - Miền Nam)",  "filename": "nu-ke-cam-xuc.wav"},
        {"provider": "vieneu", "voiceKey": "Xuân Vĩnh (Nam - Miền Nam)", "filename": "nam-cao-trao.wav"},
        # F5
        {"provider": "f5", "voiceKey": "nu_review_cuon",     "filename": "nu-review-cuon.wav"},
        {"provider": "f5", "voiceKey": "nam_review_luc",      "filename": "nam-review-luc.wav"},
        {"provider": "f5", "voiceKey": "nu_ke_chuyen_sau",    "filename": "nu-ke-chuyen-sau.wav"},
        {"provider": "f5", "voiceKey": "nam_cao_trao_gat",    "filename": "nam-cao-trao-gat.wav"},
    ]

    # 1. Clean existing samples
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
        print(f"Cleaned {OUTPUT_ROOT}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # 2. Check backend is up
    try:
        req = urllib.request.Request(f"{BASE_URL}/voice/options", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            options = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"ERROR: Cannot reach backend at {BASE_URL}: {exc}", file=sys.stderr)
        return 1

    results: dict[str, list[dict]] = {"vieneu": [], "f5": []}
    failed = 0

    for job in jobs:
        provider = job["provider"]
        voice_key = job["voiceKey"]
        filename = job["filename"]
        text = SAMPLE_TEXTS.get(voice_key, "Xin chào, đây là giọng mẫu thử.")

        out_dir = OUTPUT_ROOT / provider
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        print(f"  [{provider}] {voice_key} -> {filename} ... ", end="", flush=True)
        try:
            t0 = time.perf_counter()
            audio = post_voice_generate(text, provider, voice_key)
            elapsed = time.perf_counter() - t0
            out_path.write_bytes(audio)
            dur, sr = wav_info(out_path)
            print(f"OK  {elapsed:.1f}s  ({dur:.1f}s audio, {sr}Hz, {len(audio)//1024}KB)")
            results[provider].append({
                "voiceKey": voice_key,
                "filename": filename,
                "text": text,
                "generationTimeSec": round(elapsed, 2),
                "audioDurationSec": round(dur, 2),
                "sampleRate": sr,
                "fileSizeBytes": len(audio),
            })
        except Exception as exc:
            print(f"FAIL: {exc}")
            failed += 1
            results[provider].append({
                "voiceKey": voice_key,
                "filename": filename,
                "error": str(exc),
            })

    # 3. Write manifest
    manifest_path = OUTPUT_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifest written to {manifest_path}")
    print(f"Total: {sum(len(v) for v in results.values())} presets, {failed} failures.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
