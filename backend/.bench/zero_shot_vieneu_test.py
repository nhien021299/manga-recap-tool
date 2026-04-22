import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_SITE = ROOT / ".bench" / "vieneu-venv" / "Lib" / "site-packages"
if VENV_SITE.exists() and str(VENV_SITE) not in sys.path:
    sys.path.append(str(VENV_SITE))

from vieneu import Vieneu


MODEL_ID = "pnnbao-ump/VieNeu-TTS-0.3B"
VOICE_ROOT = ROOT / ".models" / "vieneu-voices"
VOICES_FILE = VOICE_ROOT / "voices.json"
VOICE_KEY = "voice_default"
OUT_DIR = ROOT / ".bench" / "samples" / "vieneu"
OUT_PATH = OUT_DIR / "vieneu_0_3b_voice_default.wav"

TEXT = (
    "Sau khi tỉnh lại, cậu nhận ra mọi thứ xung quanh đã hoàn toàn thay đổi. "
    "Ngôi làng yên bình ngày nào giờ chỉ còn lại đống đổ nát và sự im lặng đáng sợ. "
    "Nhưng điều khiến cậu rùng mình hơn cả, là cảm giác có thứ gì đó vẫn đang dõi theo mình, "
    "từ trong bóng tối."
)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(
        {
            "mode": "standard",
            "model_id": MODEL_ID,
            "voices_file_exists": VOICES_FILE.exists(),
            "voices_file": str(VOICES_FILE),
            "voice_key": VOICE_KEY,
            "out_path": str(OUT_PATH),
        }
    )

    tts = Vieneu(mode="standard", backbone_repo=MODEL_ID, backbone_device="cpu")
    try:
        load_from_file = getattr(tts, "_load_voices_from_file", None)
        if not callable(load_from_file):
            raise RuntimeError("Current VieNeu client does not support loading local voices.json.")
        if not VOICES_FILE.exists():
            raise FileNotFoundError(f"Missing voices manifest: {VOICES_FILE}")

        load_from_file(VOICES_FILE)
        voice_data = tts.get_preset_voice(VOICE_KEY)
        audio = tts.infer(text=TEXT, voice=voice_data, temperature=0.7)
        tts.save(audio, str(OUT_PATH))
    finally:
        tts.close()

    print({"saved": str(OUT_PATH), "size_bytes": OUT_PATH.stat().st_size})


if __name__ == "__main__":
    main()
