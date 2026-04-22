"""Generate the production preview sample for the active VieNeu preset via the backend API."""
from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.request
import wave
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000/api/v1"
OUTPUT_ROOT = Path(__file__).resolve().parent / "samples"
VOICE_CACHE_ROOT = Path(__file__).resolve().parents[1] / ".models" / "voice-cache"
TIMEOUT = 600  # seconds per request
PROJECT_DEFAULT_VOICE_KEY = "voice_default"


def build_project_default_sample_text() -> str:
    reference_text_path = VOICE_CACHE_ROOT / PROJECT_DEFAULT_VOICE_KEY / "reference.txt"
    if not reference_text_path.exists():
        raise FileNotFoundError(f"Missing project default voice text: {reference_text_path}")

    reference_text = " ".join(reference_text_path.read_text(encoding="utf-8").split())
    if not reference_text:
        raise ValueError(f"Empty project default voice text: {reference_text_path}")
    return reference_text


def post_voice_generate(text: str, provider: str, voice_key: str, speed: float = 1.0) -> bytes:
    payload = json.dumps(
        {
            "text": text,
            "provider": provider,
            "voiceKey": voice_key,
            "speed": speed,
        },
        ensure_ascii=False,
    ).encode("utf-8")
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    jobs: list[dict[str, str]] = [
        {"provider": "vieneu", "voiceKey": PROJECT_DEFAULT_VOICE_KEY, "filename": "voice-default.wav"},
    ]

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
        print(f"Cleaned {OUTPUT_ROOT}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    try:
        req = urllib.request.Request(f"{BASE_URL}/voice/options", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as exc:
        print(f"ERROR: Cannot reach backend at {BASE_URL}: {exc}", file=sys.stderr)
        return 1

    results: dict[str, list[dict[str, object]]] = {"vieneu": []}
    failed = 0
    text = build_project_default_sample_text()

    for job in jobs:
        provider = job["provider"]
        voice_key = job["voiceKey"]
        filename = job["filename"]

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
            results[provider].append(
                {
                    "voiceKey": voice_key,
                    "filename": filename,
                    "text": text,
                    "generationTimeSec": round(elapsed, 2),
                    "audioDurationSec": round(dur, 2),
                    "sampleRate": sr,
                    "fileSizeBytes": len(audio),
                }
            )
        except Exception as exc:
            print(f"FAIL: {exc}")
            failed += 1
            results[provider].append(
                {
                    "voiceKey": voice_key,
                    "filename": filename,
                    "error": str(exc),
                }
            )

    manifest_path = OUTPUT_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifest written to {manifest_path}")
    print(f"Total: {sum(len(v) for v in results.values())} presets, {failed} failures.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
