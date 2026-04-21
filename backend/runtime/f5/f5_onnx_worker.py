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


def convert_char_to_pinyin(text_list: list[str]) -> list[list[str]]:
    if not jieba.dt.initialized:
        jieba.default_logger.setLevel(50)
        jieba.initialize()

    final_text_list: list[list[str]] = []
    custom_trans = str.maketrans({";": ",", "“": '"', "”": '"', "‘": "'", "’": "'"})

    def is_chinese(char: str) -> bool:
        return "\u3100" <= char <= "\u9fff"

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


def normalize_text_for_vocab(text: str, vocab: set[str]) -> str:
    normalized_chars: list[str] = []
    for char in text:
        if char in vocab or char in {" ", "\n", "\r", "\t"}:
            normalized_chars.append(char)
            continue

        folded = unicodedata.normalize("NFKD", char)
        candidate = "".join(part for part in folded if not unicodedata.combining(part))
        appended = False
        for part in candidate:
            if part in vocab:
                normalized_chars.append(part)
                appended = True
        if appended:
            continue
        if char in {".", ",", "?", "!", ":", ";", "-", "'", '"', "(", ")"}:
            normalized_chars.append(char)
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


def generate(bundle_dir: Path, provider: str, reference_audio: Path, reference_text_file: Path, input_json: Path, output_wav: Path) -> dict[str, object]:
    ort.set_seed(DEFAULT_SEED)
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    vocab_char_map, vocab_chars = load_vocab()
    ref_text = normalize_text_for_vocab(reference_text_file.read_text(encoding="utf-8").strip(), vocab_chars)
    gen_text = normalize_text_for_vocab(str(payload["text"]).strip(), vocab_chars)
    speed = float(payload.get("speed", 1.0) or 1.0)

    preprocess = create_session(bundle_dir / "F5_Preprocess.onnx", "CPUExecutionProvider")
    transformer = create_session(bundle_dir / "F5_Transformer.onnx", provider)
    decoder = create_session(bundle_dir / "F5_Decode.onnx", "CPUExecutionProvider")

    audio = load_audio(reference_audio)
    zh_pause_punc = r"。，、；：？！"
    ref_text_len = len(ref_text.encode("utf-8")) + 3 * len(re.findall(zh_pause_punc, ref_text))
    gen_text_len = len(gen_text.encode("utf-8")) + 3 * len(re.findall(zh_pause_punc, gen_text))
    ref_audio_len = audio.shape[-1] // HOP_LENGTH + 1
    max_duration = np.array([ref_audio_len + int(ref_audio_len / max(ref_text_len, 1) * gen_text_len / max(speed, 0.1))], dtype=np.int64)
    text_ids = list_str_to_idx(convert_char_to_pinyin([f"{ref_text}. {gen_text}"]), vocab_char_map)

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
    sf.write(str(output_wav), generated_signal.reshape(-1), MODEL_SAMPLE_RATE, format="WAV")
    return {
        "normalizedReferenceText": ref_text,
        "normalizedText": gen_text,
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
