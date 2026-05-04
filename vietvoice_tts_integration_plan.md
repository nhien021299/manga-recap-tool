# VietVoice-TTS DirectML Integration Plan for Manga Recap Tool

## 0. Goal

Tích hợp `VietVoice-TTS` thẳng vào backend của `manga-recap-tool` để thay thế việc chạy CMD thủ công ở folder `D:\VietVoice-TTS`.

Mục tiêu bắt buộc:

- Backend chạy VietVoice-TTS bằng GPU AMD qua `onnxruntime-directml`, giống cách đã test CMD thành công.
- Luôn dùng clone voice mặc định từ 2 file:
  - `reference.wav`
  - `reference.txt`
- Có thể mở rộng thêm nhiều reference voice sau này.
- Text TTS phải được chunk nhỏ trước khi generate.
- Mỗi chunk không vượt quá `100` ký tự.
- Chunk không được làm mất chữ, mất dấu tiếng Việt, hoặc cắt câu đến mức mất nghĩa.
- Generate từng chunk thành `.wav`, sau đó nối lại bằng `ffmpeg concat`.
- File audio cuối phải chuẩn: mono, 44100 Hz, loudness normalize nhẹ.
- Chống AMD GPU timeout bằng rule sleep/retry/concurrency.
- Không chạy song song nhiều TTS job trên cùng GPU.

---

## 1. Repo context

Repo hiện tại:

```txt
https://github.com/nhien021299/manga-recap-tool
```

Kiến trúc hiện tại theo README:

```txt
web-app/  = React + Vite editor
backend/  = FastAPI service
```

Flow hiện tại:

```txt
Upload / Extract
  -> Script generation
  -> Backend TTS
  -> Backend render/export bằng ffmpeg
```

TTS hiện tại đang dùng provider `vieneu`, model `pnnbao-ump/VieNeu-TTS-0.3B`, voice key `voice_default`.

Plan này thêm provider mới:

```txt
vietvoice
```

Sau khi tích hợp xong, backend có thể chọn:

```env
AI_BACKEND_TTS_PROVIDER=vietvoice
```

---

## 2. Final architecture

Không gọi CMD kiểu:

```txt
python -m vietvoicetts ...
```

trực tiếp từ app production.

Thay vào đó:

```txt
backend FastAPI
  -> Voice route hiện có
    -> TTS provider registry
      -> VietVoiceService singleton
        -> TTSEngine load model 1 lần
        -> split text thành chunk <= 100 chars
        -> generate từng chunk wav
        -> sleep chống AMD timeout
        -> ffmpeg concat + loudnorm + 44100Hz mono
        -> trả audio_path về pipeline
```

Lý do:

- Tránh load model lại mỗi câu.
- Dễ retry chunk lỗi.
- Dễ cache output.
- Dễ kiểm soát timeout AMD DirectML.
- Dễ nối wav và mastering thống nhất.
- Dễ tích hợp nhiều reference voice sau này.

---

## 3. Target folder layout

Tạo cấu trúc này trong backend:

```txt
backend/
  app/
    services/
      tts/
        vietvoice/
          __init__.py
          vietvoice_service.py
          vietvoice_config.py
          vietvoice_provider.py
          text_chunker.py
          audio_joiner.py
          voice_registry.py
          refs/
            voice_default/
              reference.wav
              reference.txt
          outputs/
```

Copy package VietVoice gốc vào backend theo một trong hai cách.

### Option A, khuyên dùng cho giai đoạn đầu

Copy nguyên package:

```txt
D:\VietVoice-TTS\vietvoicetts
```

vào:

```txt
backend/app/services/tts/vietvoice/vendor/vietvoicetts
```

Ưu điểm:

- Agent sửa trực tiếp được provider DirectML.
- Không phụ thuộc folder `D:\VietVoice-TTS`.
- Dễ đóng gói theo repo.

### Option B, dùng editable install nội bộ

Đưa `VietVoice-TTS` vào:

```txt
backend/third_party/VietVoice-TTS
```

Sau đó install:

```cmd
cd backend
.venv\Scripts\activate
pip install -e third_party\VietVoice-TTS
```

Ưu điểm:

- Ít sửa import.
- Gần với cách chạy CMD ban đầu.

Khuyến nghị: dùng **Option A** nếu agent cần tự quản toàn bộ trong repo.

---

## 4. Reference voice mặc định

Copy 2 file clone voice mặc định vào:

```txt
backend/app/services/tts/vietvoice/refs/voice_default/reference.wav
backend/app/services/tts/vietvoice/refs/voice_default/reference.txt
```

Rule:

- `reference.wav` phải là giọng sạch, không nhạc nền, không SFX, không echo rõ.
- `reference.txt` phải khớp chính xác từng chữ với audio.
- Luôn đọc `reference.txt` bằng UTF-8.
- Không hardcode nội dung transcript trong code.
- Không truyền `--group` chung với custom reference, vì VietVoice logic gốc không cho dùng `reference_audio/reference_text` đồng thời với `group/gender/area/emotion`.

Voice registry mở rộng sau này:

```txt
refs/
  voice_default/
    reference.wav
    reference.txt
  voice_ngoc_huyen/
    reference.wav
    reference.txt
  voice_male_story/
    reference.wav
    reference.txt
```

---

## 5. Required dependencies

Trong venv backend:

```cmd
cd /d <repo_root>\backend
.venv\Scripts\activate

pip uninstall -y onnxruntime onnxruntime-gpu
pip install onnxruntime-directml==1.20.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install numpy tqdm soundfile librosa
```

Không cài:

```txt
onnxruntime-gpu
```

Vì máy AMD không dùng CUDA.

Kiểm tra provider:

```cmd
python -c "import onnxruntime as ort; print(ort.__version__); print(ort.get_available_providers())"
```

Kỳ vọng:

```txt
1.20.1
['DmlExecutionProvider', 'CPUExecutionProvider']
```

---

## 6. Patch VietVoice provider để dùng AMD DirectML

Trong file VietVoice gốc:

```txt
vietvoicetts/core/model.py
```

Tìm hàm:

```python
def _get_optimal_providers(self) -> List[str]:
```

Thay bằng:

```python
def _get_optimal_providers(self) -> List[str]:
    """Get the fastest available providers for Windows AMD/NVIDIA/CPU."""
    available_providers = onnxruntime.get_available_providers()
    print("ORT available providers:", available_providers)

    provider_priority = [
        "DmlExecutionProvider",
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]

    selected_providers = []
    for provider in provider_priority:
        if provider in available_providers:
            selected_providers.append(provider)

    if "CPUExecutionProvider" not in selected_providers:
        selected_providers.append("CPUExecutionProvider")

    print("ORT selected providers:", selected_providers)
    return selected_providers
```

Trong đoạn tạo session:

```python
session = onnxruntime.InferenceSession(
    model_bytes,
    sess_options=session_opts,
    providers=self.providers
)
```

Thêm log debug:

```python
print(f"{model_name} session providers:", session.get_providers())
```

Khi backend start và load model, log đúng phải là:

```txt
ORT available providers: ['DmlExecutionProvider', 'CPUExecutionProvider']
ORT selected providers: ['DmlExecutionProvider', 'CPUExecutionProvider']
preprocess session providers: ['DmlExecutionProvider', 'CPUExecutionProvider']
transformer session providers: ['DmlExecutionProvider', 'CPUExecutionProvider']
decode session providers: ['DmlExecutionProvider', 'CPUExecutionProvider']
```

Nếu log chỉ có:

```txt
CPUExecutionProvider
```

thì GPU chưa được dùng.

---

## 7. Environment variables

Thêm vào:

```txt
backend/.env
```

```env
AI_BACKEND_TTS_PROVIDER=vietvoice
AI_BACKEND_TTS_VIETVOICE_RUNTIME=directml
AI_BACKEND_TTS_VIETVOICE_VOICE_KEY=voice_default
AI_BACKEND_TTS_VIETVOICE_REF_ROOT=app/services/tts/vietvoice/refs
AI_BACKEND_TTS_VIETVOICE_OUTPUT_ROOT=.temp/tts-vietvoice
AI_BACKEND_TTS_VIETVOICE_MAX_CHARS_PER_CHUNK=100
AI_BACKEND_TTS_VIETVOICE_SHORT_SLEEP_SECONDS=0.5
AI_BACKEND_TTS_VIETVOICE_BATCH_SLEEP_EVERY=8
AI_BACKEND_TTS_VIETVOICE_BATCH_SLEEP_SECONDS=3
AI_BACKEND_TTS_VIETVOICE_ERROR_SLEEP_SECONDS=12
AI_BACKEND_TTS_MAX_CONCURRENT_JOBS=1
AI_BACKEND_RENDER_FFMPEG_PATH=ffmpeg
```

Rule:

```txt
AI_BACKEND_TTS_MAX_CONCURRENT_JOBS=1
```

là bắt buộc với AMD DirectML để tránh driver timeout khi batch lớn.

---

## 8. Text chunking rules

Mỗi narration line phải được chia thành các chunk nhỏ.

Hard rule:

```txt
MAX_CHARS_PER_CHUNK = 100
```

Chunker phải giữ nguyên tiếng Việt:

- Không bỏ dấu.
- Không normalize kiểu làm mất ký tự tiếng Việt.
- Không encode/decode sai UTF-8.
- Không cắt giữa một từ.
- Không cắt mất dấu câu gốc nếu dấu câu đó giúp ngắt nghĩa.
- Không làm rơi chữ khi nối các chunk lại.
- Không tự rewrite câu.
- Không tự dịch.
- Không tự thay tên nhân vật.

Ưu tiên cắt theo thứ tự:

```txt
1. Dấu kết câu: . ! ? … 。！？ 
2. Dấu ngắt vừa: , ; : ，；：
3. Khoảng trắng gần nhất trước mốc 100 ký tự
4. Nếu từ quá dài bất thường, giữ nguyên từ đó trong một chunk riêng
```

Mỗi chunk nên có dấu câu cuối. Nếu chunk không có dấu câu cuối, có thể thêm dấu `.` vào **bản gửi TTS**, nhưng không được sửa text gốc trong JSON.

Ví dụ input:

```txt
Tô Minh đứng chết lặng giữa màn mưa máu. Trước mắt hắn, bí mật bị chôn giấu suốt nhiều năm cuối cùng cũng lộ ra. Nhưng điều đáng sợ nhất là, kẻ đứng sau tất cả vẫn chưa hề xuất hiện.
```

Output chunk:

```txt
1. Tô Minh đứng chết lặng giữa màn mưa máu.
2. Trước mắt hắn, bí mật bị chôn giấu suốt nhiều năm cuối cùng cũng lộ ra.
3. Nhưng điều đáng sợ nhất là, kẻ đứng sau tất cả vẫn chưa hề xuất hiện.
```

---

## 9. text_chunker.py

Tạo file:

```txt
backend/app/services/tts/vietvoice/text_chunker.py
```

Nội dung:

```python
from __future__ import annotations

import re
from typing import List


class VietnameseSafeTextChunker:
    def __init__(self, max_chars: int = 100):
        if max_chars < 40:
            raise ValueError("max_chars should be >= 40 to preserve Vietnamese phrase meaning.")
        self.max_chars = max_chars

    def normalize_spaces(self, text: str) -> str:
        text = text.replace("\ufeff", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n+", " ", text)
        return text.strip()

    def chunk(self, text: str) -> List[str]:
        text = self.normalize_spaces(text)
        if not text:
            return []

        sentences = self._split_keep_delimiters(text, r"([.!?…。！？]+)")
        chunks: List[str] = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(sentence) <= self.max_chars:
                chunks.append(sentence)
                continue

            chunks.extend(self._split_long_sentence(sentence))

        return [self._ensure_tts_sentence_end(c) for c in chunks if c.strip()]

    def _split_keep_delimiters(self, text: str, delimiter_pattern: str) -> List[str]:
        parts = re.split(delimiter_pattern, text)
        result: List[str] = []
        buffer = ""

        for part in parts:
            if part is None or part == "":
                continue

            buffer += part

            if re.fullmatch(delimiter_pattern, part):
                result.append(buffer.strip())
                buffer = ""

        if buffer.strip():
            result.append(buffer.strip())

        return result

    def _split_long_sentence(self, sentence: str) -> List[str]:
        comma_parts = self._split_keep_delimiters(sentence, r"([,;:，；：]+)")
        chunks: List[str] = []
        buffer = ""

        for part in comma_parts:
            part = part.strip()
            if not part:
                continue

            candidate = f"{buffer} {part}".strip() if buffer else part

            if len(candidate) <= self.max_chars:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer.strip())
                    buffer = ""

                if len(part) <= self.max_chars:
                    buffer = part
                else:
                    chunks.extend(self._split_by_space(part))

        if buffer:
            chunks.append(buffer.strip())

        return chunks

    def _split_by_space(self, text: str) -> List[str]:
        words = text.split(" ")
        chunks: List[str] = []
        buffer = ""

        for word in words:
            word = word.strip()
            if not word:
                continue

            candidate = f"{buffer} {word}".strip() if buffer else word

            if len(candidate) <= self.max_chars:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer.strip())
                buffer = word

        if buffer:
            chunks.append(buffer.strip())

        return chunks

    def _ensure_tts_sentence_end(self, text: str) -> str:
        text = text.strip()
        if not text:
            return text

        if text[-1] not in ".!?…。！？,;:，；：":
            return text + "."
        return text
```

---

## 10. audio_joiner.py

Tạo file:

```txt
backend/app/services/tts/vietvoice/audio_joiner.py
```

Nội dung:

```python
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List


class AudioJoiner:
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def concat_wavs_44100_mono_loudnorm(self, wav_paths: List[Path], output_path: Path) -> None:
        if not wav_paths:
            raise ValueError("No wav files to concatenate.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        list_path = output_path.with_suffix(".concat.txt")

        lines = []
        for wav_path in wav_paths:
            if not wav_path.exists() or wav_path.stat().st_size <= 1000:
                raise FileNotFoundError(f"Invalid wav chunk: {wav_path}")

            normalized = str(wav_path.resolve()).replace("\\", "/")
            lines.append(f"file '{normalized}'")

        list_path.write_text("\n".join(lines), encoding="utf-8")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=9",
            "-ar",
            "44100",
            "-ac",
            "1",
            str(output_path),
        ]

        subprocess.run(cmd, check=True)
```

Đây là bản sạch và nhẹ hơn, tương đương lệnh đã test:

```cmd
ffmpeg -y -f concat -safe 0 -i "D:\VietVoice-TTS\outputs\list.txt" -af "loudnorm=I=-16:TP=-1.5:LRA=9" -ar 44100 -ac 1 "D:\VietVoice-TTS\outputs\clone_recap_test_joined_44100.wav"
```

---

## 11. voice_registry.py

Tạo file:

```txt
backend/app/services/tts/vietvoice/voice_registry.py
```

Nội dung:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VietVoiceReference:
    voice_key: str
    reference_audio: Path
    reference_text: str


class VietVoiceRegistry:
    def __init__(self, ref_root: Path):
        self.ref_root = ref_root

    def get(self, voice_key: str) -> VietVoiceReference:
        voice_dir = self.ref_root / voice_key
        reference_audio = voice_dir / "reference.wav"
        reference_text_path = voice_dir / "reference.txt"

        if not reference_audio.exists():
            raise FileNotFoundError(f"Missing reference audio: {reference_audio}")

        if not reference_text_path.exists():
            raise FileNotFoundError(f"Missing reference text: {reference_text_path}")

        reference_text = reference_text_path.read_text(encoding="utf-8").strip()
        if not reference_text:
            raise ValueError(f"Empty reference text: {reference_text_path}")

        return VietVoiceReference(
            voice_key=voice_key,
            reference_audio=reference_audio,
            reference_text=reference_text,
        )
```

---

## 12. vietvoice_config.py

Tạo file:

```txt
backend/app/services/tts/vietvoice/vietvoice_config.py
```

Nội dung:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


@dataclass(frozen=True)
class VietVoiceConfig:
    repo_backend_root: Path
    provider: str
    runtime: str
    voice_key: str
    ref_root: Path
    output_root: Path
    ffmpeg_path: str
    max_chars_per_chunk: int
    short_sleep_seconds: float
    batch_sleep_every: int
    batch_sleep_seconds: float
    error_sleep_seconds: float

    @staticmethod
    def from_env(repo_backend_root: Path) -> "VietVoiceConfig":
        ref_root_raw = os.getenv(
            "AI_BACKEND_TTS_VIETVOICE_REF_ROOT",
            "app/services/tts/vietvoice/refs",
        )
        output_root_raw = os.getenv(
            "AI_BACKEND_TTS_VIETVOICE_OUTPUT_ROOT",
            ".temp/tts-vietvoice",
        )

        return VietVoiceConfig(
            repo_backend_root=repo_backend_root,
            provider=os.getenv("AI_BACKEND_TTS_PROVIDER", "vietvoice"),
            runtime=os.getenv("AI_BACKEND_TTS_VIETVOICE_RUNTIME", "directml"),
            voice_key=os.getenv("AI_BACKEND_TTS_VIETVOICE_VOICE_KEY", "voice_default"),
            ref_root=(repo_backend_root / ref_root_raw).resolve(),
            output_root=(repo_backend_root / output_root_raw).resolve(),
            ffmpeg_path=os.getenv("AI_BACKEND_RENDER_FFMPEG_PATH", "ffmpeg"),
            max_chars_per_chunk=_get_int("AI_BACKEND_TTS_VIETVOICE_MAX_CHARS_PER_CHUNK", 100),
            short_sleep_seconds=_get_float("AI_BACKEND_TTS_VIETVOICE_SHORT_SLEEP_SECONDS", 0.5),
            batch_sleep_every=_get_int("AI_BACKEND_TTS_VIETVOICE_BATCH_SLEEP_EVERY", 8),
            batch_sleep_seconds=_get_float("AI_BACKEND_TTS_VIETVOICE_BATCH_SLEEP_SECONDS", 3.0),
            error_sleep_seconds=_get_float("AI_BACKEND_TTS_VIETVOICE_ERROR_SLEEP_SECONDS", 12.0),
        )
```

---

## 13. vietvoice_service.py

Tạo file:

```txt
backend/app/services/tts/vietvoice/vietvoice_service.py
```

Nội dung:

```python
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from threading import Lock
from typing import List, Optional

from .audio_joiner import AudioJoiner
from .text_chunker import VietnameseSafeTextChunker
from .vietvoice_config import VietVoiceConfig
from .voice_registry import VietVoiceRegistry

# Adjust this import depending on where the VietVoice package is placed.
# Option A example:
from .vendor.vietvoicetts.core.tts_engine import TTSEngine


class VietVoiceService:
    def __init__(self, config: VietVoiceConfig):
        self.config = config
        self.registry = VietVoiceRegistry(config.ref_root)
        self.chunker = VietnameseSafeTextChunker(max_chars=config.max_chars_per_chunk)
        self.joiner = AudioJoiner(ffmpeg_path=config.ffmpeg_path)
        self.engine = TTSEngine()
        self.config.output_root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def synthesize(
        self,
        text: str,
        output_name: str,
        voice_key: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Path:
        voice_key = voice_key or self.config.voice_key
        reference = self.registry.get(voice_key)
        chunks = self.chunker.chunk(text)

        if not chunks:
            raise ValueError("Empty TTS text after chunking.")

        safe_output_name = self._safe_output_name(output_name)
        job_folder_name = job_id or self._hash_text(f"{voice_key}|{text}")[:16]
        job_dir = self.config.output_root / job_folder_name
        job_dir.mkdir(parents=True, exist_ok=True)

        final_path = job_dir / safe_output_name

        if final_path.exists() and final_path.stat().st_size > 1000:
            return final_path

        with self._lock:
            chunk_paths: List[Path] = []

            for index, chunk in enumerate(chunks, start=1):
                chunk_path = job_dir / f"chunk_{index:03d}.wav"
                chunk_paths.append(chunk_path)

                if chunk_path.exists() and chunk_path.stat().st_size > 1000:
                    continue

                self._generate_chunk_with_retry(
                    chunk=chunk,
                    chunk_path=chunk_path,
                    reference_audio=str(reference.reference_audio),
                    reference_text=reference.reference_text,
                )

                time.sleep(self.config.short_sleep_seconds)

                if index % self.config.batch_sleep_every == 0:
                    time.sleep(self.config.batch_sleep_seconds)

            self.joiner.concat_wavs_44100_mono_loudnorm(chunk_paths, final_path)

        return final_path

    def _generate_chunk_with_retry(
        self,
        chunk: str,
        chunk_path: Path,
        reference_audio: str,
        reference_text: str,
    ) -> None:
        try:
            self.engine.synthesize(
                text=chunk,
                output_path=str(chunk_path),
                reference_audio=reference_audio,
                reference_text=reference_text,
            )
        except Exception:
            time.sleep(self.config.error_sleep_seconds)
            self.engine.synthesize(
                text=chunk,
                output_path=str(chunk_path),
                reference_audio=reference_audio,
                reference_text=reference_text,
            )

        if not chunk_path.exists() or chunk_path.stat().st_size <= 1000:
            raise RuntimeError(f"TTS chunk generation failed or produced invalid wav: {chunk_path}")

    def _safe_output_name(self, output_name: str) -> str:
        name = Path(output_name).name
        if not name.lower().endswith(".wav"):
            name += ".wav"
        return name

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

---

## 14. vietvoice_provider.py

Tạo file:

```txt
backend/app/services/tts/vietvoice/vietvoice_provider.py
```

Nội dung:

```python
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .vietvoice_config import VietVoiceConfig
from .vietvoice_service import VietVoiceService


@lru_cache(maxsize=1)
def get_vietvoice_service() -> VietVoiceService:
    # backend/app/services/tts/vietvoice/vietvoice_provider.py
    backend_root = Path(__file__).resolve().parents[4]
    config = VietVoiceConfig.from_env(backend_root)
    return VietVoiceService(config)
```

Nếu path backend root bị lệch, agent cần chỉnh lại bằng cách in:

```python
print(Path(__file__).resolve().parents)
```

---

## 15. Integrate with existing voice route

Tìm route hiện tại xử lý:

```txt
POST /api/v1/voice/generate
```

Hiện route này đang gọi provider `vieneu`.

Thêm nhánh provider:

```python
from app.services.tts.vietvoice.vietvoice_provider import get_vietvoice_service


def generate_voice_with_provider(text: str, output_name: str, voice_key: str | None = None) -> str:
    provider = settings.tts_provider

    if provider == "vietvoice":
        service = get_vietvoice_service()
        output_path = service.synthesize(
            text=text,
            output_name=output_name,
            voice_key=voice_key,
        )
        return str(output_path)

    if provider == "vieneu":
        # existing flow
        ...

    raise ValueError(f"Unsupported TTS provider: {provider}")
```

Input từ frontend vẫn có thể giữ:

```json
{
  "text": "Tô Minh đứng chết lặng giữa màn mưa máu.",
  "voice_key": "voice_default"
}
```

Nếu frontend chưa truyền `voice_key`, backend dùng mặc định:

```txt
voice_default
```

---

## 16. Integrate with script JSON pipeline

Nếu script output đang là list theo panel:

```json
[
  {
    "image_id": "img_001",
    "narration": "Tô Minh đứng chết lặng giữa màn mưa máu."
  }
]
```

Agent thêm audio path:

```python
for item in script_items:
    image_id = item["image_id"]
    narration = item["narration"]

    output_path = vietvoice_service.synthesize(
        text=narration,
        output_name=f"{image_id}.wav",
        voice_key="voice_default",
        job_id=chapter_id,
    )

    item["audio_path"] = str(output_path)
```

Result:

```json
{
  "image_id": "img_001",
  "narration": "Tô Minh đứng chết lặng giữa màn mưa máu.",
  "audio_path": "backend/.temp/tts-vietvoice/chapter_001/img_001.wav"
}
```

---

## 17. AMD DirectML runtime rules

Bắt buộc:

```txt
TTS concurrency = 1
```

Không chạy cùng lúc:

```txt
ComfyUI/ZLUDA image generation
VietVoice DirectML TTS batch
```

Recommended sleep:

```txt
Sau mỗi chunk: 0.5s
Sau mỗi 8 chunk: 3s
Sau lỗi hoặc GPU timeout: 12s rồi retry 1 lần
```

Chunk length:

```txt
<= 100 chars
```

Nếu vẫn gặp AMD popup:

```txt
1. Giảm max chunk còn 80 chars
2. Tăng short sleep lên 0.8s
3. Tăng batch sleep lên 5s
4. Đảm bảo ComfyUI đã tắt
5. Restart backend để reload DirectML session sạch
```

---

## 18. Optional quality tweak: nfe_step

Nếu VietVoice có file:

```txt
vietvoicetts/core/model_config.py
```

Tìm:

```python
nfe_step
```

Rule:

```txt
32 = chất lượng tốt hơn, dễ timeout hơn
24 = sweet spot
16 = nhanh, ổn định hơn, chất lượng giảm nhẹ
```

Khuyến nghị mặc định:

```txt
nfe_step = 24
```

Chỉ giảm xuống `16` nếu AMD vẫn timeout với chunk <= 100 chars.

---

## 19. API smoke test

Sau khi tích hợp, chạy backend:

```cmd
cd /d <repo_root>
npm run dev:be
```

Hoặc:

```cmd
cd /d <repo_root>\backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Test provider bằng curl:

```cmd
curl -X POST "http://127.0.0.1:8000/api/v1/voice/generate" ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Tô Minh đứng chết lặng giữa màn mưa máu. Trước mắt hắn, bí mật cuối cùng cũng lộ ra.\",\"voice_key\":\"voice_default\"}"
```

Kỳ vọng:

```txt
- Backend log có DmlExecutionProvider
- Có file wav output
- File cuối 44100 Hz, mono
- Không popup AMD driver
- Không bị cụt cuối câu
```

---

## 20. Local standalone backend test script

Tạo file:

```txt
backend/.bench/test_vietvoice_backend.py
```

Nội dung:

```python
from app.services.tts.vietvoice.vietvoice_provider import get_vietvoice_service


def main():
    service = get_vietvoice_service()

    output = service.synthesize(
        text=(
            "Tô Minh đứng chết lặng giữa màn mưa máu. "
            "Trước mắt hắn, bí mật bị chôn giấu suốt nhiều năm cuối cùng cũng lộ ra. "
            "Nhưng điều đáng sợ nhất là, kẻ đứng sau tất cả vẫn chưa hề xuất hiện."
        ),
        output_name="clone_recap_test_joined_44100.wav",
        voice_key="voice_default",
        job_id="bench_vietvoice",
    )

    print("Generated:", output)


if __name__ == "__main__":
    main()
```

Chạy:

```cmd
cd /d <repo_root>\backend
.venv\Scripts\activate
python .bench\test_vietvoice_backend.py
```

Expected:

```txt
DmlExecutionProvider
Generated: ...clone_recap_test_joined_44100.wav
```

---

## 21. Do not use group/style with clone reference

VietVoice có group/style:

```txt
story
news
audiobook
interview
review
```

Nhưng với clone voice mặc định, không dùng:

```txt
--group story
```

vì custom reference đã quyết định voice/style. Nếu vừa truyền `reference_audio/reference_text` vừa truyền `group`, code gốc có thể báo lỗi.

Production default:

```txt
reference clone only
```

Sau này nếu muốn test built-in style, tạo provider mode khác:

```env
AI_BACKEND_TTS_VIETVOICE_MODE=builtin
```

Nhưng không đưa vào pipeline chính lúc này.

---

## 22. Error handling

Nếu chunk generate lỗi:

```txt
sleep 12s
retry 1 lần
```

Nếu retry vẫn lỗi:

- Mark panel/audio item là failed.
- Ghi rõ chunk text bị lỗi.
- Không làm mất toàn bộ chapter.
- Cho phép resume từ chunk đã có.

Output chunk đã tồn tại và size > 1000 bytes thì skip generate lại.

Nếu final concat lỗi:

- Kiểm tra file list `.concat.txt`.
- Kiểm tra path có dấu backslash Windows không.
- Dùng forward slash trong concat list.
- Kiểm tra `ffmpeg` có trong PATH.

---

## 23. Resume/cache rule

Job folder:

```txt
backend/.temp/tts-vietvoice/<chapter_id>/
```

Mỗi panel:

```txt
img_001.wav
img_002.wav
```

Mỗi panel có chunk file:

```txt
chunk_001.wav
chunk_002.wav
chunk_003.wav
```

Nếu chạy lại:

- chunk nào có rồi thì bỏ qua.
- final wav có rồi thì trả luôn.
- chỉ regenerate file lỗi hoặc thiếu.

---

## 24. Acceptance checklist for agent

Agent chỉ được xem task hoàn tất khi đạt đủ:

- [ ] Backend cài `onnxruntime-directml==1.20.1`.
- [ ] Không còn `onnxruntime-gpu`.
- [ ] Log backend hiện `DmlExecutionProvider`.
- [ ] VietVoice model load 1 lần qua singleton.
- [ ] Provider `vietvoice` có thể chọn bằng env.
- [ ] Luôn dùng `reference.wav` + `reference.txt` mặc định.
- [ ] Có `voice_registry` để thêm reference voice mới sau này.
- [ ] Chunker giữ tiếng Việt, không mất chữ, không vượt quá 100 chars.
- [ ] Mỗi chunk generate riêng `.wav`.
- [ ] Có sleep 0.5s sau mỗi chunk.
- [ ] Có sleep 3s sau mỗi 8 chunk.
- [ ] Có retry sau lỗi với sleep 12s.
- [ ] Concurrency TTS = 1.
- [ ] Nối wav bằng ffmpeg concat.
- [ ] Final wav là 44100 Hz, mono.
- [ ] Final wav dùng `loudnorm=I=-16:TP=-1.5:LRA=9`.
- [ ] API `/api/v1/voice/generate` chạy được với provider `vietvoice`.
- [ ] Script JSON sau TTS có `audio_path`.
- [ ] Không cần chạy CMD ở `D:\VietVoice-TTS` nữa.
- [ ] ComfyUI/ZLUDA không chạy song song khi batch TTS.

---

## 25. Final production flow

```txt
Script JSON narration
  -> VietVoice provider selected
  -> voice_default reference loaded
  -> text chunked <= 100 chars
  -> TTSEngine synthesize chunk_001.wav
  -> sleep 0.5s
  -> TTSEngine synthesize chunk_002.wav
  -> sleep 0.5s
  -> every 8 chunks sleep 3s
  -> ffmpeg concat
  -> loudnorm + 44100Hz + mono
  -> output panel wav
  -> attach audio_path to JSON
  -> render/export uses audio_path
```

This is the target: backend chạy giống CMD đã test thành công, nhưng sạch hơn, an toàn hơn, có cache/retry, và sẵn sàng mở rộng nhiều reference voice.
