from __future__ import annotations

import asyncio
import math
import subprocess
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.core.config import BACKEND_ROOT, Settings
from app.models.api import RenderClipSpec, RenderPlanRequest
from app.models.render_jobs import RenderJobRecord

SILENT_AUDIO_RATE = 24000
DEFAULT_FRAME_RATE = 30


class NativeFfmpegRenderService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ffmpeg_path_cache: str | None = None
        self._font_path_cache: str | None = None

    def resolve_ffmpeg_path(self) -> str | None:
        if self._ffmpeg_path_cache:
            return self._ffmpeg_path_cache

        candidate = (self.settings.render_ffmpeg_path or "ffmpeg").strip() or "ffmpeg"
        direct_path = Path(candidate)
        if direct_path.is_absolute() or "\\" in candidate or "/" in candidate:
            resolved = direct_path if direct_path.is_absolute() else (BACKEND_ROOT / direct_path).resolve()
            if resolved.exists():
                self._ffmpeg_path_cache = str(resolved)
                return self._ffmpeg_path_cache
            return None

        located = shutil.which(candidate)
        if located:
            self._ffmpeg_path_cache = located
        return located

    def assert_available(self) -> str:
        ffmpeg_path = self.resolve_ffmpeg_path()
        if ffmpeg_path:
            return ffmpeg_path
        raise FileNotFoundError(
            "Native ffmpeg is not available for backend export. Set AI_BACKEND_RENDER_FFMPEG_PATH to a valid ffmpeg binary."
        )

    def build_download_url(self, job_id: str) -> str:
        return f"{self.settings.api_prefix}/render/jobs/{job_id}/result"

    async def prepare_job(
        self,
        job_id: str,
        plan: RenderPlanRequest,
        clips: list[RenderClipSpec],
        files: list[UploadFile],
    ) -> RenderJobRecord:
        self.assert_available()
        self._validate_clip_specs(clips)

        temp_dir = self.settings.render_temp_root / job_id
        assets_dir = temp_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        output_path = temp_dir / "output.mp4"

        try:
            asset_files = await self._save_asset_files(assets_dir, files)
            self._validate_asset_mapping(clips, asset_files)
            job = RenderJobRecord(
                job_id=job_id,
                plan=plan,
                clips=sorted(clips, key=lambda clip: clip.orderIndex),
                temp_dir=temp_dir,
                asset_files=asset_files,
                output_path=output_path,
            )
            job.add_log("request", f"Accepted backend render request for {len(clips)} clips.")
            job.set_progress(0, phase="accepted", detail="Queued for native ffmpeg export.")
            return job
        except Exception:
            self.cleanup_job_dir(temp_dir)
            raise

    def finalize_job(self, job: RenderJobRecord) -> None:
        if job.status.value == "completed":
            self._prune_completed_job_dir(job)
            return
        self.cleanup_job_dir(job.temp_dir)

    def expire_job(self, job: RenderJobRecord) -> bool:
        if not job.is_expired():
            return False
        self.cleanup_job_dir(job.temp_dir)
        return True

    async def cancel_running_job(self, job: RenderJobRecord) -> None:
        process = job.current_process
        if process is None or process.poll() is not None:
            return
        process.kill()
        with suppress(ProcessLookupError):
            await asyncio.to_thread(process.wait)

    async def render(self, job: RenderJobRecord) -> None:
        ffmpeg_path = self.assert_available()
        segments: list[Path] = []
        generated_files: list[Path] = []
        total_clips = len(job.clips)

        if total_clips == 0:
            raise ValueError("Render request must include at least one clip.")

        job.set_progress(8, phase="preparing assets", detail=f"Preparing {total_clips} clips.")
        job.add_log("request", "Preparing render assets.")

        try:
            for index, clip in enumerate(job.clips, start=1):
                self._ensure_not_cancelled(job)

                frame_pattern = job.temp_dir / f"clip-{index:03d}-frame-%05d.png"
                segment_path = job.temp_dir / f"segment-{index:03d}.mp4"
                frame_paths = await self._render_clip_frames(
                    job=job,
                    clip=clip,
                    clip_index=index,
                    total_clips=total_clips,
                    source_path=job.asset_files[clip.panelFileKey],
                    frame_pattern=frame_pattern,
                )
                generated_files.extend(frame_paths)
                job.add_log("request", f"Rendering clip {index}/{total_clips}.", clip.clipId)

                audio_path = job.asset_files.get(clip.audioFileKey) if clip.audioFileKey else None
                try:
                    await self._run_ffmpeg_segment(
                        ffmpeg_path=ffmpeg_path,
                        job=job,
                        clip=clip,
                        frame_pattern=frame_pattern,
                        audio_path=audio_path,
                        segment_path=segment_path,
                    )
                except Exception as exc:
                    details = self._build_clip_debug_details(
                        ffmpeg_path=ffmpeg_path,
                        clip=clip,
                        frame_pattern=frame_pattern,
                        frame_count=len(frame_paths),
                        audio_path=audio_path,
                        segment_path=segment_path,
                    )
                    job.add_log("error", f"Clip {index}/{total_clips} render failed.", details)
                    exc_text = str(exc).strip() or repr(exc)
                    raise RuntimeError(f"{exc_text}\n\n{details}") from exc
                segments.append(segment_path)
                generated_files.append(segment_path)
                for frame_path in frame_paths:
                    frame_path.unlink(missing_ok=True)

            self._ensure_not_cancelled(job)
            concat_file = job.temp_dir / "concat.txt"
            concat_file.write_text(
                "\n".join(f"file '{segment.as_posix()}'" for segment in segments),
                encoding="utf-8",
            )
            generated_files.append(concat_file)

            job.set_progress(88, phase="muxing final video", detail="Concatenating rendered clips.")
            await self._run_ffmpeg_concat(ffmpeg_path=ffmpeg_path, job=job, concat_file=concat_file, output_path=job.output_path)
            job.set_progress(96, phase="finalizing", detail="Finalizing MP4 output.")
            job.add_log("result", "Render finished successfully.", str(job.output_path))
        finally:
            for path in generated_files:
                if path == job.output_path:
                    continue
                path.unlink(missing_ok=True)

    def cleanup_job_dir(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    def _prune_completed_job_dir(self, job: RenderJobRecord) -> None:
        if not job.temp_dir.exists():
            return
        for child in job.temp_dir.iterdir():
            if child == job.output_path:
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def _validate_clip_specs(self, clips: list[RenderClipSpec]) -> None:
        if not clips:
            raise ValueError("Render request must include at least one clip.")
        seen_clip_ids: set[str] = set()
        for clip in clips:
            if clip.clipId in seen_clip_ids:
                raise ValueError(f"Duplicate render clipId: {clip.clipId}")
            seen_clip_ids.add(clip.clipId)
            if not clip.panelFileKey.strip():
                raise ValueError(f"Clip {clip.clipId} is missing panelFileKey.")

    async def _save_asset_files(self, assets_dir: Path, files: list[UploadFile]) -> dict[str, Path]:
        if not files:
            raise ValueError("Render request must upload at least one asset file.")

        saved: dict[str, Path] = {}
        for index, file in enumerate(files, start=1):
            filename = (file.filename or "").strip()
            if not filename:
                raise ValueError(f"Uploaded render file #{index} is missing a filename.")
            key = Path(filename).stem.strip()
            if not key:
                raise ValueError(f"Uploaded render file '{filename}' has an invalid key.")
            if key in saved:
                raise ValueError(f"Duplicate uploaded render asset key: {key}")
            suffix = Path(filename).suffix or ".bin"
            destination = assets_dir / f"{key}{suffix}"
            destination.write_bytes(await file.read())
            saved[key] = destination
        return saved

    def _validate_asset_mapping(self, clips: Iterable[RenderClipSpec], asset_files: dict[str, Path]) -> None:
        referenced_keys: set[str] = set()
        for clip in clips:
            referenced_keys.add(clip.panelFileKey)
            if clip.audioFileKey:
                referenced_keys.add(clip.audioFileKey)

        missing = sorted(key for key in referenced_keys if key not in asset_files)
        extra = sorted(key for key in asset_files if key not in referenced_keys)
        if missing:
            raise ValueError(f"Missing uploaded render assets for keys: {', '.join(missing)}")
        if extra:
            raise ValueError(f"Unexpected uploaded render assets: {', '.join(extra)}")

    def _ensure_not_cancelled(self, job: RenderJobRecord) -> None:
        if job.cancel_requested:
            raise RuntimeError("Render cancelled by user.")

    def _describe_file(self, path: Path | None) -> str:
        if path is None:
            return "None"
        exists = path.exists()
        size = path.stat().st_size if exists else "missing"
        return f"{path} (exists={exists}, size={size})"

    def _build_clip_debug_details(
        self,
        ffmpeg_path: str,
        clip: RenderClipSpec,
        frame_pattern: Path,
        frame_count: int,
        audio_path: Path | None,
        segment_path: Path,
    ) -> str:
        return "\n".join(
            [
                f"clipId: {clip.clipId}",
                f"panelId: {clip.panelId}",
                f"durationMs: {clip.durationMs}",
                f"holdAfterMs: {clip.holdAfterMs}",
                f"captionChars: {len(clip.captionText.strip())}",
                f"ffmpegPath: {ffmpeg_path}",
                f"framePattern: {frame_pattern}",
                f"frameCount: {frame_count}",
                f"audio: {self._describe_file(audio_path)}",
                f"segment: {segment_path}",
            ]
        )

    def _ease_in_out(self, progress: float) -> float:
        return 0.5 - math.cos(math.pi * progress) / 2

    def _get_motion_transform(
        self,
        clip: RenderClipSpec,
        progress: float,
        draw_width: float,
        draw_height: float,
    ) -> tuple[float, float, float]:
        eased = self._ease_in_out(progress)
        intensity = max(0.5, min(1.0, clip.motionIntensity or 0.8))
        pan_x = draw_width * (0.04 + intensity * 0.03)
        pan_y = draw_height * (0.03 + intensity * 0.025)
        preset = clip.motionPreset or "push_in_center"

        if preset == "push_in_upper_focus":
            return 1.04 + intensity * 0.09 * eased, 0.0, pan_y * eased
        if preset == "push_in_lower_focus":
            return 1.04 + intensity * 0.09 * eased, 0.0, -pan_y * eased
        if preset == "drift_left_to_right":
            return 1.05 + intensity * 0.05 * eased, pan_x * (eased * 2 - 1), 0.0
        if preset == "drift_right_to_left":
            return 1.05 + intensity * 0.05 * eased, -pan_x * (eased * 2 - 1), 0.0
        if preset == "rise_up_focus":
            return 1.04 + intensity * 0.07 * eased, 0.0, pan_y * (0.4 - eased)
        if preset == "pull_back_reveal":
            return 1.12 - intensity * 0.08 * eased, 0.0, -pan_y * 0.25 * eased
        return 1.04 + intensity * 0.08 * eased, 0.0, 0.0

    def _draw_vignette(self, width: int, height: int) -> Image.Image:
        vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette)
        center_x = width / 2
        center_y = height / 2
        max_radius = max(width, height) * 0.72

        for step in range(10, 0, -1):
            ratio = step / 10
            radius_x = int(max_radius * ratio)
            radius_y = int(max_radius * ratio)
            alpha = int((1 - ratio) * 22)
            draw.ellipse(
                [center_x - radius_x, center_y - radius_y, center_x + radius_x, center_y + radius_y],
                outline=(0, 0, 0, alpha),
                width=max(1, int(width * 0.015)),
            )
        return vignette

    def _resolve_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if self._font_path_cache is None:
            candidates = [
                Path(ImageFont.__file__).resolve().parent / "fonts" / "DejaVuSans.ttf",
                Path("C:/Windows/Fonts/arial.ttf"),
                Path("C:/Windows/Fonts/segoeui.ttf"),
            ]
            for candidate in candidates:
                if candidate.exists():
                    self._font_path_cache = str(candidate)
                    break
            else:
                self._font_path_cache = ""

        if self._font_path_cache:
            return ImageFont.truetype(self._font_path_cache, size=size)
        return ImageFont.load_default()

    def _wrap_caption_lines(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int,
        max_lines: int = 4,
    ) -> list[str]:
        words = [word for word in text.split() if word]
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break

        if current and len(lines) < max_lines:
            lines.append(current)
        return lines

    def _compose_frame(
        self,
        clip: RenderClipSpec,
        plan: RenderPlanRequest,
        source_path: Path,
        output_path: Path,
        progress: float,
    ) -> None:
        with Image.open(source_path) as source_image:
            source = source_image.convert("RGB")
            width = plan.outputWidth
            height = plan.outputHeight

            canvas = Image.new("RGB", (width, height), "#080b12")
            background = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
            bg_scale, bg_offset_x, bg_offset_y = self._get_motion_transform(clip, min(1.0, progress * 0.85), width, height)
            scaled_bg = background.resize(
                (
                    max(1, int(width * max(1.0, bg_scale * 1.01))),
                    max(1, int(height * max(1.0, bg_scale * 1.01))),
                ),
                resample=Image.Resampling.LANCZOS,
            )
            background_canvas = Image.new("RGB", (width, height), "#080b12")
            background_canvas.paste(
                scaled_bg,
                (
                    int((width - scaled_bg.width) / 2 + bg_offset_x * 0.3),
                    int((height - scaled_bg.height) / 2 + bg_offset_y * 0.3),
                ),
            )
            background = background_canvas
            background = background.filter(ImageFilter.GaussianBlur(radius=24))
            background = ImageEnhance.Brightness(background).enhance(0.35)
            canvas.paste(background, (0, 0))

            overlay = Image.new("RGBA", (width, height), (6, 10, 18, 122))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

            safe_width = int(width * 0.88)
            safe_height = int(height * (0.68 if plan.captionMode == "burned" and clip.captionText.strip() else 0.8))
            main = ImageOps.contain(source, (safe_width, safe_height), method=Image.Resampling.LANCZOS)
            scale, offset_x, offset_y = self._get_motion_transform(clip, progress, main.width, main.height)
            animated_main = main.resize(
                (
                    max(1, int(main.width * scale)),
                    max(1, int(main.height * scale)),
                ),
                resample=Image.Resampling.LANCZOS,
            )

            draw_x = int((width - animated_main.width) / 2 + offset_x)
            draw_y = int(
                (
                    max(height * 0.1, (height - animated_main.height) / 2 - height * 0.06)
                    if plan.captionMode == "burned" and clip.captionText.strip()
                    else (height - animated_main.height) / 2
                )
                + offset_y
            )

            shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                [draw_x - 18, draw_y - 18, draw_x + animated_main.width + 18, draw_y + animated_main.height + 18],
                radius=32,
                fill=(0, 0, 0, 110),
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
            canvas = Image.alpha_composite(canvas, shadow)
            canvas.paste(animated_main.convert("RGBA"), (draw_x, draw_y), animated_main.convert("RGBA"))
            canvas = Image.alpha_composite(canvas, self._draw_vignette(width, height))

            if plan.captionMode == "burned" and clip.captionText.strip():
                draw = ImageDraw.Draw(canvas)
                font = self._resolve_font(max(22, round(width * 0.028)))
                padding_x = round(width * 0.075)
                max_text_width = width - padding_x * 2
                lines = self._wrap_caption_lines(draw, clip.captionText.strip(), font, max_text_width)
                if lines:
                    line_height = max(30, round(width * 0.038))
                    box_height = line_height * len(lines) + 34
                    box_y = height - box_height - round(height * 0.06)
                    draw.rounded_rectangle(
                        [padding_x - 18, box_y - 16, padding_x + max_text_width + 18, box_y + box_height],
                        radius=28,
                        fill=(4, 8, 15, 214),
                    )
                    for line_index, line in enumerate(lines):
                        draw.text(
                            (padding_x, box_y + line_index * line_height),
                            line,
                            font=font,
                            fill="#f4f7fb",
                        )

            canvas.convert("RGB").save(output_path, format="PNG")

    async def _render_clip_frames(
        self,
        job: RenderJobRecord,
        clip: RenderClipSpec,
        clip_index: int,
        total_clips: int,
        source_path: Path,
        frame_pattern: Path,
    ) -> list[Path]:
        frame_rate = max(job.plan.frameRate, DEFAULT_FRAME_RATE)
        total_frames = max(1, round((clip.durationMs / 1000) * frame_rate))
        frame_paths: list[Path] = []
        clip_progress_span = 56 / max(total_clips, 1)
        base_progress = 15 + ((clip_index - 1) / max(total_clips, 1)) * 56

        for frame_index in range(total_frames):
            self._ensure_not_cancelled(job)
            progress = 1.0 if total_frames == 1 else frame_index / max(total_frames - 1, 1)
            frame_path = frame_pattern.with_name(frame_pattern.name.replace("%05d", f"{frame_index + 1:05d}"))
            await asyncio.to_thread(
                self._compose_frame,
                clip,
                job.plan,
                source_path,
                frame_path,
                progress,
            )
            frame_paths.append(frame_path)

            if frame_index == 0 or frame_index == total_frames - 1 or frame_index % max(1, round(frame_rate / 2)) == 0:
                job.set_progress(
                    round(base_progress + (frame_index / max(total_frames, 1)) * clip_progress_span * 0.72),
                    phase=f"animating clip {clip_index}/{total_clips}",
                    detail=f"Animating clip {clip_index}/{total_clips}.",
                )

        return frame_paths

    async def _run_ffmpeg_segment(
        self,
        ffmpeg_path: str,
        job: RenderJobRecord,
        clip: RenderClipSpec,
        frame_pattern: Path,
        audio_path: Path | None,
        segment_path: Path,
    ) -> None:
        clip_position = clip.orderIndex + 1
        total_clips = max(len(job.clips), 1)
        job.set_progress(
            min(95, 15 + round((clip_position / total_clips) * 56)),
            phase=f"encoding clip {clip_position}/{total_clips}",
            detail=f"Encoding clip {clip_position}/{total_clips}.",
        )
        clip_seconds = f"{clip.durationMs / 1000:.3f}"
        command = [
            "-y",
            "-framerate",
            str(job.plan.frameRate),
            "-i",
            str(frame_pattern),
        ]

        if audio_path is not None:
            command.extend(
                [
                    "-i",
                    str(audio_path),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-t",
                    clip_seconds,
                    "-vf",
                    f"fps={job.plan.frameRate},format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-af",
                    f"apad=pad_dur={clip.holdAfterMs / 1000:.3f}",
                    str(segment_path),
                ]
            )
        else:
            command.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"anullsrc=channel_layout=stereo:sample_rate={SILENT_AUDIO_RATE}",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-t",
                    clip_seconds,
                    "-vf",
                    f"fps={job.plan.frameRate},format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    str(segment_path),
                ]
            )

        await self._run_ffmpeg_command(ffmpeg_path, job, command, f"Clip render failed for {clip.clipId}.")

    async def _run_ffmpeg_concat(
        self,
        ffmpeg_path: str,
        job: RenderJobRecord,
        concat_file: Path,
        output_path: Path,
    ) -> None:
        command = [
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        await self._run_ffmpeg_command(ffmpeg_path, job, command, "Final video concat failed.")

    async def _run_ffmpeg_command(
        self,
        ffmpeg_path: str,
        job: RenderJobRecord,
        command: list[str],
        error_prefix: str,
    ) -> None:
        self._ensure_not_cancelled(job)
        try:
            process = subprocess.Popen(
                [ffmpeg_path, *command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:
            exc_text = str(exc).strip() or repr(exc)
            joined_command = " ".join([ffmpeg_path, *command])
            raise RuntimeError(f"{error_prefix} {exc_text}\nCommand: {joined_command}") from exc
        job.current_process = process
        try:
            stdout, stderr = await asyncio.to_thread(process.communicate)
        except Exception as exc:
            job.current_process = None
            exc_text = str(exc).strip() or repr(exc)
            joined_command = " ".join([ffmpeg_path, *command])
            raise RuntimeError(f"{error_prefix} {exc_text}\nCommand: {joined_command}") from exc
        job.current_process = None

        if job.cancel_requested:
            raise RuntimeError("Render cancelled by user.")

        if process.returncode == 0:
            return

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        details = stderr_text or stdout_text or f"ffmpeg returned a non-zero exit code ({process.returncode})."
        joined_command = " ".join([ffmpeg_path, *command])
        raise RuntimeError(f"{error_prefix} {details}\nCommand: {joined_command}")
