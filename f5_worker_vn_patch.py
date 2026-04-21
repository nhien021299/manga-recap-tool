from __future__ import annotations

import argparse
import json
import re
import unicodedata
from importlib.resources import files
from pathlib import Path

import jieba
import numpy as np
import onnxruntime as ort
import soundfile as sf
import torch
from pydub import AudioSegment
from pypinyin import Style, lazy_pinyin


MODEL_SAMPLE_RATE = 24000
HOP_LENGTH = 256
MAX_THREADS = 8
DEVICE_ID = 0
DEFAULT_SEED = 9527

# Keep output slightly below full scale to avoid harsh clipping / crunchy peaks.
OUTPUT_PEAK_LIMIT = 0.98

# Vietnamese / Latin punctuation used for duration estimation.
LATIN_PAUSE_PUNC_RE = r"[.,;:?!…]"
# Chinese punctuation still supported when the checkpoint/frontend expects it.
ZH_PAUSE_PUNC_RE = r"[。，、；：？！]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["probe", "generate"], required=True)
    parser.add_argument("--provider", default="CPUExecutionProvider")
    parser.add_argument("--bundle-dir")
    parser.add_argument("--reference-audio")
    parser.add_argument("--reference-text-file")
    parser.add_argument("--input-json")
    parser.add_argument("--output-wav")
    parser.add_argument("--output-json", required=True)
    return parser


def get_provider_options(provider: str) -> list[dict[str, object]] | None:
    if provider == "DmlExecutionProvider":
        return [
            {
                "device_id": DEVICE_ID,
                "performance_preference": "high_performance",
                "device_filter": "any",
            }
        ]
    return None


def contains_cjk(text: str) -> bool:
    """Return True when text contains Chinese/CJK ideographs.

    We only run pinyin conversion for CJK text. Vietnamese and other Latin scripts
    should NOT go through jieba+pypinyin because that corrupts pronunciation cues.
    """
    for ch in text:
        code = ord(ch)
        if (
            0x3400 <= code <= 0x4DBF  # CJK Unified Ideographs Extension A
            or 0x4E00 <= code <= 0x9FFF  # CJK Unified Ideographs
            or 0xF900 <= code <= 0xFAFF  # CJK Compatibility Ideographs
        ):
            return True
    return False


def latin_text_to_tokens(text: str) -> list[str]:
    """Tokenize Latin/Vietnamese text conservatively.

    Do not strip Vietnamese letters into fake pinyin. Just keep characters as-is.
    Spaces are preserved so the model still sees word boundaries.
    """
    return list(text)


# Original Chinese frontend retained, but used only when real CJK text exists.
def convert_char_to_pinyin(text_list: list[str]) -> list[list[str]]:
    if not jieba.dt.initialized:
        jieba.default_logger.setLevel(50)
        jieba.initialize()

    final_text_list: list[list[str]] = []
    custom_trans = str.maketrans({";": ",", "“": '"', "”": '"', "‘": "'", "’": "'"})

    def is_chinese(char: str) -> bool:
        code = ord(char)
        return (
            0x3400 <= code <= 0x4DBF
            or 0x4E00 <= code <= 0x9FFF
            or 0xF900 <= code <= 0xFAFF
        )

    for text in text_list:
        char_list: list[str] = []
        for seg in jieba.cut(text.translate(custom_trans)):
            seg_byte_len = len(seg.encode("utf-8"))
            if seg_byte_len == len(seg):
                if char_list and seg_byte_len > 1 and char_list[-1] not in " :'\"":
                    char_list.append(" ")
                char_list.extend(seg)
            elif seg_byte_len == 3 * len(seg):
                seg_pinyin = lazy_pinyin(seg, style=Style.TONE3, tone_sandhi=True)
                for index, char in enumerate(seg):
                    if is_chinese(char):
                        char_list.append(" ")
                    char_list.append(seg_pinyin[index])
            else:
                for char in seg:
                    if ord(char) < 256:
                        char_list.extend(char)
                    elif is_chinese(char):
                        char_list.append(" ")
                        char_list.extend(lazy_pinyin(char, style=Style.TONE3, tone_sandhi=True))
                    else:
                        char_list.append(char)
        final_text_list.append(char_list)
    return final_text_list


def tokenize_text(text: str) -> list[str]:
    """Choose the right frontend per script.

    - CJK: retain original pinyin path
    - Vietnamese / Latin: keep raw chars
    """
    if contains_cjk(text):
        return convert_char_to_pinyin([text])[0]
    return latin_text_to_tokens(text)


# Keep this broad enough for Vietnamese punctuation normalization.
PUNCT_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "；": ";",
        "：": ":",
        "，": ",",
        "。": ".",
        "？": "?",
        "！": "!",
    }
)


SAFE_PUNCT = {".", ",", "?", "!", ":", ";", "-", "'", '"', "(", ")", "[", "]", "/"}


def normalize_text_for_vocab(text: str, vocab: set[str]) -> str:
    """Normalize text without destroying Vietnamese content unnecessarily.

    Priority:
    1. Keep exact char if vocab supports it.
    2. Keep spaces/newlines normalized.
    3. For punctuation, map common Unicode punctuation to ASCII equivalents.
    4. Only fall back to accent-folded Latin forms as a last resort.

    Note: if the vocab truly lacks Vietnamese characters, pronunciation quality can
    still suffer. This patch avoids the earlier aggressive corruption path, but the
    correct long-term fix is still using the matching VN/multilingual checkpoint + vocab.
    """
    text = text.translate(PUNCT_TRANSLATION)
    normalized_chars: list[str] = []

    for char in text:
        if char in vocab or char in {" ", "\n", "\r", "\t"}:
            normalized_chars.append(char)
            continue

        if char in SAFE_PUNCT:
            normalized_chars.append(char)
            continue

        # Last-resort compatibility fold.
        folded = unicodedata.normalize("NFKD", char)
        candidate = "".join(part for part in folded if not unicodedata.combining(part))

        appended = False
        for part in candidate:
            if part in vocab:
                normalized_chars.append(part)
                appended = True

        # If we could not preserve the character and it is unknown to vocab,
        # drop it instead of inventing fake pinyin / fake phonemes.
        if not appended:
            continue

    normalized = "".join(normalized_chars)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def list_str_to_idx(texts: list[list[str]], vocab_char_map: dict[str, int], padding_value: int = -1) -> np.ndarray:
    sequences = [torch.tensor([vocab_char_map.get(char, 0) for char in text], dtype=torch.int32) for text in texts]
    padded = torch.nn.utils.rnn.pad_sequence(sequences, padding_value=padding_value, batch_first=True)
    return padded.numpy()


def load_vocab() -> tuple[dict[str, int], set[str]]:
    vocab_path = files("f5_tts").joinpath("infer/examples/vocab.txt")
    vocab_char_map: dict[str, int] = {}
    with open(vocab_path, "r", encoding="utf-8") as handle:
        for index, char in enumerate(handle):
            vocab_char_map[char.rstrip("\n")] = index
    return vocab_char_map, set(vocab_char_map)


def create_session(model_path: Path, provider: str) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.log_severity_level = 4
    options.log_verbosity_level = 4
    options.inter_op_num_threads = MAX_THREADS
    options.intra_op_num_threads = MAX_THREADS
    options.enable_cpu_mem_arena = True
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.add_session_config_entry("session.set_denormal_as_zero", "1")
    options.add_session_config_entry("optimization.enable_gelu_approximation", "1")
    options.add_session_config_entry("disable_synchronize_execution_providers", "1")
    providers = [provider] if provider != "CPUExecutionProvider" else ["CPUExecutionProvider"]
    return ort.InferenceSession(
        str(model_path),
        sess_options=options,
        providers=providers,
        provider_options=get_provider_options(provider),
    )


def load_audio(path: Path) -> np.ndarray:
    audio = AudioSegment.from_file(path).set_channels(1).set_frame_rate(MODEL_SAMPLE_RATE)
    samples = np.array(audio.get_array_of_samples(), dtype=np.int16)
    return samples.reshape(1, 1, -1)


def estimate_text_length(text: str) -> int:
    """More script-agnostic duration proxy.

    The old code weighted only Chinese punctuation. Here we count bytes plus pause
    punctuation for both Latin and Chinese punctuation families.
    """
    pause_count = len(re.findall(LATIN_PAUSE_PUNC_RE, text)) + len(re.findall(ZH_PAUSE_PUNC_RE, text))
    return len(text.encode("utf-8")) + 3 * pause_count


def limit_audio_peak(signal: np.ndarray, peak_limit: float = OUTPUT_PEAK_LIMIT) -> np.ndarray:
    signal = signal.astype(np.float32, copy=False).reshape(-1)
    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    if peak > peak_limit and peak > 0:
        signal = signal * (peak_limit / peak)
    return signal


def generate(bundle_dir: Path, provider: str, reference_audio: Path, reference_text_file: Path, input_json: Path, output_wav: Path) -> dict[str, object]:
    ort.set_seed(DEFAULT_SEED)
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    vocab_char_map, vocab_chars = load_vocab()

    ref_text_raw = reference_text_file.read_text(encoding="utf-8").strip()
    gen_text_raw = str(payload["text"]).strip()

    ref_text = normalize_text_for_vocab(ref_text_raw, vocab_chars)
    gen_text = normalize_text_for_vocab(gen_text_raw, vocab_chars)
    speed = float(payload.get("speed", 1.0) or 1.0)

    preprocess = create_session(bundle_dir / "F5_Preprocess.onnx", "CPUExecutionProvider")
    transformer = create_session(bundle_dir / "F5_Transformer.onnx", provider)
    decoder = create_session(bundle_dir / "F5_Decode.onnx", "CPUExecutionProvider")

    audio = load_audio(reference_audio)

    ref_text_len = estimate_text_length(ref_text)
    gen_text_len = estimate_text_length(gen_text)
    ref_audio_len = audio.shape[-1] // HOP_LENGTH + 1
    max_duration = np.array(
        [ref_audio_len + int(ref_audio_len / max(ref_text_len, 1) * gen_text_len / max(speed, 0.1))],
        dtype=np.int64,
    )

    combined_text = f"{ref_text}. {gen_text}" if gen_text else ref_text
    token_list = tokenize_text(combined_text)
    text_ids = list_str_to_idx([token_list], vocab_char_map)

    preprocess_outputs = preprocess.run(
        None,
        {
            preprocess.get_inputs()[0].name: audio,
            preprocess.get_inputs()[1].name: text_ids,
            preprocess.get_inputs()[2].name: max_duration,
        },
    )
    noise, rope_cos_q, rope_sin_q, rope_cos_k, rope_sin_k, cat_mel_text, cat_mel_text_drop, ref_signal_len = preprocess_outputs

    time_step = np.array([0], dtype=np.int32)
    nfe_step = 32
    for _ in range(0, nfe_step - 1):
        noise, time_step = transformer.run(
            None,
            {
                transformer.get_inputs()[0].name: noise,
                transformer.get_inputs()[1].name: rope_cos_q,
                transformer.get_inputs()[2].name: rope_sin_q,
                transformer.get_inputs()[3].name: rope_cos_k,
                transformer.get_inputs()[4].name: rope_sin_k,
                transformer.get_inputs()[5].name: cat_mel_text,
                transformer.get_inputs()[6].name: cat_mel_text_drop,
                transformer.get_inputs()[7].name: time_step,
            },
        )

    generated_signal = decoder.run(
        None,
        {
            decoder.get_inputs()[0].name: noise,
            decoder.get_inputs()[1].name: ref_signal_len,
        },
    )[0]

    generated = limit_audio_peak(generated_signal)
    sf.write(str(output_wav), generated, MODEL_SAMPLE_RATE, format="WAV")

    return {
        "referenceTextRaw": ref_text_raw,
        "normalizedReferenceText": ref_text,
        "inputTextRaw": gen_text_raw,
        "normalizedText": gen_text,
        "combinedText": combined_text,
        "usedChineseFrontend": contains_cjk(combined_text),
        "executionProvider": provider,
        "outputPath": str(output_wav),
    }


def main() -> int:
    args = build_parser().parse_args()
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "probe":
        output_json.write_text(
            json.dumps(
                {
                    "availableProviders": ort.get_available_providers(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 0

    if not all([args.bundle_dir, args.reference_audio, args.reference_text_file, args.input_json, args.output_wav]):
        output_json.write_text(json.dumps({"error": "Missing generate arguments."}), encoding="utf-8")
        return 1

    try:
        payload = generate(
            bundle_dir=Path(args.bundle_dir),
            provider=args.provider,
            reference_audio=Path(args.reference_audio),
            reference_text_file=Path(args.reference_text_file),
            input_json=Path(args.input_json),
            output_wav=Path(args.output_wav),
        )
    except Exception as exc:
        output_json.write_text(
            json.dumps(
                {
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1

    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
