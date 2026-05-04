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
