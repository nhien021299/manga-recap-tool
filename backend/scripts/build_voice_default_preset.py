from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
VOICE_CACHE_ROOT = BACKEND_ROOT / ".models" / "voice-cache"
VOICE_PRESET_ROOT = BACKEND_ROOT / ".models" / "vieneu-voices"
DEFAULT_MODEL_ID = "pnnbao-ump/VieNeu-TTS-0.3B"
VIENEU_VENV_SITE = BACKEND_ROOT / ".bench" / "vieneu-venv" / "Lib" / "site-packages"

if VIENEU_VENV_SITE.exists() and str(VIENEU_VENV_SITE) not in sys.path:
    sys.path.append(str(VIENEU_VENV_SITE))

from vieneu import Vieneu


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a cached VieNeu-TTS-0.3B standard preset from a reference wav/txt pair.")
    parser.add_argument("--source-key", default="voice_default", help="Voice cache key containing reference.wav and reference.txt.")
    parser.add_argument("--voice-key", default="voice_default", help="Output preset key written to voices.json.")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Hugging Face model id for VieNeu-TTS-0.3B standard.")
    parser.add_argument("--device", default="cpu", choices=["cpu", "gpu"], help="Backbone device to use while encoding the reference.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_root = VOICE_CACHE_ROOT / args.source_key
    reference_audio = source_root / "reference.wav"
    reference_text = source_root / "reference.txt"

    if not reference_audio.exists():
        raise FileNotFoundError(f"Missing reference wav: {reference_audio}")
    if not reference_text.exists():
        raise FileNotFoundError(f"Missing reference text: {reference_text}")

    transcript = " ".join(reference_text.read_text(encoding="utf-8").split())
    if not transcript:
        raise ValueError(f"Reference text is empty: {reference_text}")

    VOICE_PRESET_ROOT.mkdir(parents=True, exist_ok=True)

    tts = Vieneu(mode="standard", backbone_repo=args.model_id, backbone_device=args.device)
    try:
        ref_codes = tts.encode_reference(str(reference_audio))
        code_list = [int(value) for value in ref_codes.flatten().tolist()]
    finally:
        tts.close()

    voices_payload = {
        "default_voice": args.voice_key,
        "presets": {
            args.voice_key: {
                "codes": code_list,
                "text": transcript,
                "description": f"Cached standard preset built from {args.source_key}/reference.wav for {args.model_id}.",
            }
        },
    }
    (VOICE_PRESET_ROOT / "voices.json").write_text(
        json.dumps(voices_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest_payload = {
        "version": 2,
        "defaultVoiceKey": args.voice_key,
        "fallbacks": {
            "default": args.voice_key,
            "voice_2_clone": args.voice_key,
            args.voice_key: args.voice_key,
        },
        "voices": {
            args.voice_key: {
                "sourcePath": (
                    os.path.relpath(source_root / "source.mp3", VOICE_PRESET_ROOT).replace("\\", "/")
                    if (source_root / "source.mp3").exists()
                    else None
                ),
                "referencePath": os.path.relpath(reference_audio, VOICE_PRESET_ROOT).replace("\\", "/"),
                "transcriptPath": os.path.relpath(reference_text, VOICE_PRESET_ROOT).replace("\\", "/"),
                "modelId": args.model_id,
            }
        },
    }
    (VOICE_PRESET_ROOT / "clone-cache.json").write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    shutil.copyfile(reference_audio, VOICE_PRESET_ROOT / f"{args.voice_key}.wav")
    (VOICE_PRESET_ROOT / f"{args.voice_key}.txt").write_text(transcript, encoding="utf-8")

    print(
        json.dumps(
            {
                "voiceKey": args.voice_key,
                "sourceKey": args.source_key,
                "modelId": args.model_id,
                "codes": len(code_list),
                "voicesJson": str(VOICE_PRESET_ROOT / "voices.json"),
                "manifestJson": str(VOICE_PRESET_ROOT / "clone-cache.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
