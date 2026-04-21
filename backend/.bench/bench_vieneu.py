from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path


DEFAULT_TEXT = "Xin chao, day la mau benchmark TTS de so sanh Vieneu va F5 trong flow backend."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark backend TTS providers through the active API contract.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1", help="Backend API root.")
    parser.add_argument(
        "--provider",
        action="append",
        dest="providers",
        help="Provider to benchmark. Repeat to run multiple providers. Defaults to vieneu and f5.",
    )
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Benchmark text.")
    parser.add_argument("--speed", type=float, default=1.0, help="Voice speed.")
    parser.add_argument(
        "--output-root",
        default=str(Path(__file__).resolve().parent / "samples"),
        help="Output directory for samples and JSON.",
    )
    parser.add_argument("--timeout", type=int, default=1800, help="HTTP timeout in seconds.")
    return parser


def fetch_json(url: str, timeout: int) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json_for_bytes(url: str, payload: dict[str, object], timeout: int) -> bytes:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "audio/wav",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def wav_duration_seconds(path: Path) -> tuple[float, int]:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        sample_rate = handle.getframerate()
    duration = frames / float(sample_rate) if sample_rate else 0.0
    return duration, sample_rate


def main() -> int:
    args = build_parser().parse_args()
    base_url = args.base_url.rstrip("/")
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    providers_to_run = args.providers or ["vieneu", "f5"]

    try:
        options_payload = fetch_json(f"{base_url}/voice/options", timeout=args.timeout)
    except urllib.error.URLError as exc:
        print(f"Failed to reach backend voice options endpoint: {exc}", file=sys.stderr)
        return 1

    provider_map = {item["id"]: item for item in options_payload.get("providers", [])}
    results: dict[str, object] = {
        "baseUrl": base_url,
        "text": args.text,
        "providers": {},
    }

    for provider_id in providers_to_run:
        option = provider_map.get(provider_id)
        if option is None:
            print(f"Skipping unknown provider '{provider_id}'.", file=sys.stderr)
            continue
        if not option.get("enabled"):
            status_message = option.get("statusMessage") or "provider is disabled"
            print(f"Skipping provider '{provider_id}': {status_message}", file=sys.stderr)
            results["providers"][provider_id] = {
                "enabled": False,
                "statusMessage": status_message,
            }
            continue

        voices = option.get("voices") or []
        voice_key = option.get("defaultVoiceKey") or (voices[0]["key"] if voices else None)
        if not voice_key:
            print(f"Skipping provider '{provider_id}': no voice preset is available.", file=sys.stderr)
            continue

        runtime_url = f"{base_url}/system/tts?{urllib.parse.urlencode({'provider': provider_id})}"
        runtime_payload = fetch_json(runtime_url, timeout=args.timeout)

        provider_output_dir = output_root / provider_id
        provider_output_dir.mkdir(parents=True, exist_ok=True)
        sample_path = provider_output_dir / "sample.wav"

        try:
            start = time.perf_counter()
            audio_bytes = post_json_for_bytes(
                f"{base_url}/voice/generate",
                {
                    "text": args.text,
                    "provider": provider_id,
                    "voiceKey": voice_key,
                    "speed": args.speed,
                },
                timeout=args.timeout,
            )
            elapsed = time.perf_counter() - start
            sample_path.write_bytes(audio_bytes)
            duration, sample_rate = wav_duration_seconds(sample_path)

            results["providers"][provider_id] = {
                "enabled": True,
                "voiceKey": voice_key,
                "samplePath": str(sample_path),
                "generationTimeSec": elapsed,
                "audioDurationSec": duration,
                "realTimeFactor": (elapsed / duration) if duration else None,
                "sampleRate": sample_rate,
                "fileSizeBytes": sample_path.stat().st_size,
                "runtime": runtime_payload,
            }
            print(f"{provider_id}: wrote {sample_path} in {elapsed:.2f}s")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            results["providers"][provider_id] = {
                "enabled": True,
                "voiceKey": voice_key,
                "runtime": runtime_payload,
                "error": {
                    "statusCode": exc.code,
                    "detail": detail,
                },
            }
            print(f"{provider_id}: request failed with HTTP {exc.code}", file=sys.stderr)
        except Exception as exc:
            results["providers"][provider_id] = {
                "enabled": True,
                "voiceKey": voice_key,
                "runtime": runtime_payload,
                "error": {
                    "detail": str(exc),
                },
            }
            print(f"{provider_id}: benchmark failed: {exc}", file=sys.stderr)

    results_path = output_root / "benchmark.json"
    results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote benchmark summary to {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
