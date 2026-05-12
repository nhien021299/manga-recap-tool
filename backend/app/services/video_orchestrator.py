"""Video production orchestrator.

Coordinates the full pipeline: TTS → Gemini direction → Remotion render.
Manages job state and progress tracking.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import subprocess
import uuid
from pathlib import Path

from app.core.config import Settings
from app.models.video import (
    BatchTtsRequest,
    BatchTtsResult,
    NarrationPackage,
    SceneTtsResult,
    VideoDirection,
    VideoJobPhase,
    VideoJobStatus,
    VideoProduceRequest,
)
from app.services.video_director_service import VideoDirectorService
from app.services.video_tts_service import VideoTtsService

logger = logging.getLogger(__name__)


class VideoOrchestrator:
    """Coordinates the video production pipeline."""

    def __init__(
        self,
        settings: Settings,
        video_tts_service: VideoTtsService,
        video_director_service: VideoDirectorService,
    ) -> None:
        self.settings = settings
        self.video_tts_service = video_tts_service
        self.video_director_service = video_director_service
        self._jobs: dict[str, _JobState] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._render_processes: dict[str, subprocess.Popen] = {}

    def _video_jobs_root(self) -> Path:
        return self.settings.render_temp_root.parent / "video-jobs"

    async def start_production(self, request: VideoProduceRequest) -> VideoJobStatus:
        """Start a video production job. Returns immediately with job ID."""
        job_id = str(uuid.uuid4())
        state = _JobState(job_id=job_id, request=request)
        self._jobs[job_id] = state

        # Run the pipeline in background
        task = asyncio.create_task(self._run_pipeline(state))
        self._tasks[job_id] = task
        
        # Cleanup task ref when done
        task.add_done_callback(lambda t: self._tasks.pop(job_id, None))

        return state.to_status()

    def purge_all_data(self) -> dict[str, int]:
        """Stop all running jobs and delete all temporary job files."""
        # 1. Stop all tasks
        cancelled_count = 0
        for job_id in list(self._render_processes):
            self._terminate_running_process(job_id)
        for task in self._tasks.values():
            task.cancel()
            cancelled_count += 1
        self._tasks.clear()

        # 2. Delete directories
        import shutil
        roots = [
            self.settings.render_temp_root,
            self._video_jobs_root()
        ]
        
        deleted_dirs = 0
        for root in roots:
            if root.exists():
                # Delete contents but keep the root if possible, 
                # or just delete and recreat
                shutil.rmtree(root)
                root.mkdir(parents=True, exist_ok=True)
                deleted_dirs += 1
        
        # 3. Clear memory state
        self._jobs.clear()
        
        return {"cancelled_tasks": cancelled_count, "purged_roots": deleted_dirs}

    def get_status(self, job_id: str) -> VideoJobStatus | None:
        """Get current status of a video production job."""
        state = self._jobs.get(job_id)
        if state is None:
            return None
        return state.to_status()

    def get_result_path(self, job_id: str) -> Path | None:
        """Get the output video path if the job is completed."""
        state = self._jobs.get(job_id)
        if state is None or state.phase != VideoJobPhase.completed:
            return None
        if state.output_path and state.output_path.exists():
            return state.output_path
        return None

    def cancel_job(self, job_id: str) -> VideoJobStatus | None:
        """Cancel a running video production job."""
        state = self._jobs.get(job_id)
        if state is None:
            return None

        if state.phase not in [VideoJobPhase.completed, VideoJobPhase.failed, VideoJobPhase.cancelled]:
            state.phase = VideoJobPhase.cancelled
            state.detail = "Production cancelled by user."
            state.progress = 0
            
            # Actually cancel the background task
            task = self._tasks.get(job_id)
            if task:
                self._terminate_running_process(job_id)
                task.cancel()
                logger.info("Video background task cancelled job_id=%s", job_id)
            
            logger.info("Video job cancelled by user job_id=%s", job_id)

        return state.to_status()

    async def _run_pipeline(self, state: _JobState) -> None:
        """Execute the full production pipeline."""
        request = state.request
        job_id = state.job_id

        try:
            package = self.video_tts_service.parse_narration_file(request.narration_path)

            if request.direction_data and request.audio_paths:
                state.phase = VideoJobPhase.directing
                state.progress = 55
                state.detail = "Using pre-generated direction and audio from UI..."
                logger.info("Video pipeline using UI pre-generated data job_id=%s", job_id)
                
                scene_results = []
                total_audio_ms = 0
                for scene in package.scenes:
                    audio_path = request.audio_paths.get(scene.scene)
                    audio_ms = 0
                    if audio_path:
                        audio_ms = self.video_tts_service._measure_audio_duration_ms(Path(audio_path))
                        
                    scene_results.append(SceneTtsResult(
                        scene=scene.scene,
                        title=scene.title,
                        audio_path=audio_path or "",
                        audio_duration_ms=audio_ms,
                        target_duration_ms=int(scene.duration_seconds * 1000),
                        narration=scene.narration,
                    ))
                    total_audio_ms += audio_ms
                    
                tts_result = BatchTtsResult(
                    job_id=job_id,
                    total_scenes=len(package.scenes),
                    total_audio_duration_ms=total_audio_ms,
                    scene_results=scene_results
                )
                state.tts_result = tts_result
                direction = VideoDirection(**request.direction_data)
                state.direction = direction
            else:
                # Phase 1: Batch TTS
                state.phase = VideoJobPhase.tts_generating
                state.progress = 5
                state.detail = "Generating TTS audio for all scenes..."
                logger.info("Video pipeline phase 1: TTS job_id=%s", job_id)

                tts_request = BatchTtsRequest(
                    narration_path=request.narration_path,
                    voice_key=request.voice_key,
                    speed=request.speed,
                    provider=request.provider,
                )

                def update_tts_progress(p: int, d: str):
                    state.progress = p
                    state.detail = d

                tts_result: BatchTtsResult = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.video_tts_service.generate_batch(
                        tts_request, job_id=job_id, on_progress=update_tts_progress
                    ),
                )

                state.tts_result = tts_result
                state.progress = 35
                state.detail = (
                    f"TTS complete: {tts_result.total_scenes} scenes, "
                    f"{tts_result.total_audio_duration_ms}ms total audio"
                )
                logger.info(
                    "Video pipeline TTS complete job_id=%s scenes=%d audio_ms=%d",
                    job_id,
                    tts_result.total_scenes,
                    tts_result.total_audio_duration_ms,
                )

                # Phase 2: Gemini Video Direction
                state.phase = VideoJobPhase.directing
                state.progress = 40
                state.detail = "Generating video direction via Gemini..."
                logger.info("Video pipeline phase 2: Direction job_id=%s", job_id)

                direction: VideoDirection = (
                    await self.video_director_service.generate_direction(
                        package=package,
                        tts_result=tts_result,
                        job_id=job_id,
                        width=request.width,
                        height=request.height,
                        fps=request.fps,
                    )
                )

                state.direction = direction
                state.progress = 55
                state.detail = (
                    f"Direction complete: {len(direction.scenes)} scenes, "
                    f"{direction.total_duration_ms}ms total"
                )
                logger.info(
                    "Video pipeline direction complete job_id=%s scenes=%d total_ms=%d",
                    job_id,
                    len(direction.scenes),
                    direction.total_duration_ms,
                )

            # Phase 3: Remotion Render
            state.phase = VideoJobPhase.rendering
            state.progress = 60
            state.detail = "Preparing Remotion render..."
            logger.info("Video pipeline phase 3: Render job_id=%s", job_id)

            output_path = await self._render_with_remotion(
                job_id=job_id,
                package=package,
                tts_result=tts_result,
                direction=direction,
                state=state,
            )

            state.output_path = output_path
            state.phase = VideoJobPhase.completed
            state.progress = 100
            state.detail = "Video production complete!"
            logger.info(
                "Video pipeline completed job_id=%s output=%s", job_id, output_path
            )

        except Exception as exc:
            state.phase = VideoJobPhase.failed
            state.error = str(exc)
            state.detail = f"Pipeline failed: {exc}"
            logger.exception("Video pipeline failed job_id=%s", job_id)

    async def _render_with_remotion(
        self,
        *,
        job_id: str,
        package: NarrationPackage,
        tts_result: BatchTtsResult,
        direction: VideoDirection,
        state: _JobState,
    ) -> Path:
        """Execute Remotion render and return the output path."""
        import json
        import shutil

        job_dir = self._video_jobs_root() / job_id
        output_path = job_dir / "output" / f"chapter_{package.chapter}_final.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Find the remotion project
        remotion_root = Path(__file__).resolve().parents[3] / "remotion"
        if not remotion_root.exists():
            raise FileNotFoundError(
                f"Remotion project not found at {remotion_root}. "
                "Run the Remotion setup first."
            )

        # Copy assets into remotion/public/ (where staticFile() resolves)
        public_dir = remotion_root / "public"
        public_dir.mkdir(parents=True, exist_ok=True)

        state.detail = "Copying assets for Remotion render..."
        state.progress = 62
        tts_map = {r.scene: r for r in tts_result.scene_results}

        scenes_manifest: list[dict] = []
        for scene in package.scenes:
            scene_num = scene.scene
            # Copy image
            src_image = Path(scene.image_path)
            if src_image.exists():
                dst_image = public_dir / f"scene_{scene_num:02d}{src_image.suffix}"
                shutil.copy2(src_image, dst_image)
            else:
                dst_image = None
                logger.warning("Scene %d image missing: %s", scene_num, src_image)

            # Copy audio
            tts = tts_map.get(scene_num)
            dst_audio = None
            dst_dialogue = None
            if tts:
                audio_src = Path(tts.audio_path)
                if audio_src.exists():
                    dst_audio = public_dir / f"scene_{scene_num:02d}.wav"
                    shutil.copy2(audio_src, dst_audio)

                if tts.dialogue_audio_path:
                    dialogue_src = Path(tts.dialogue_audio_path)
                    if dialogue_src.exists():
                        dst_dialogue = (
                            public_dir / f"scene_{scene_num:02d}_dialogue.wav"
                        )
                        shutil.copy2(dialogue_src, dst_dialogue)

            scenes_manifest.append(
                {
                    "scene": scene_num,
                    "title": scene.title,
                    "imagePath": dst_image.name if dst_image else None,
                    "audioPath": dst_audio.name if dst_audio else None,
                    "dialogueAudioPath": dst_dialogue.name if dst_dialogue else None,
                    "audioDurationMs": tts.audio_duration_ms if tts else 0,
                    "dialogueDurationMs": tts.dialogue_duration_ms if tts else None,
                }
            )

        # Build Remotion input props
        direction_data = direction.model_dump()
        direction_data["assets"] = scenes_manifest
        direction_data["publicDir"] = str(public_dir)

        props_path = job_dir / "input-props.json"
        props_path.parent.mkdir(parents=True, exist_ok=True)
        props_path.write_text(
            json.dumps(direction_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        state.detail = "Running Remotion render..."
        state.progress = 68
        logger.info("Remotion input props saved at: %s", props_path)

        # Execute Remotion render
        # CLI syntax: npx remotion render <entry> <comp-id> <output> --props=<file>
        npx_path = shutil.which("npx")
        if not npx_path:
            raise FileNotFoundError("npx not found in PATH. Install Node.js first.")

        render_cmd = [
            npx_path,
            "remotion",
            "render",
            "src/index.ts",
            "ChapterRecap",
            str(output_path),
            f"--props={props_path}",
            "--codec=h264",
            "--image-format=jpeg",
            "--jpeg-quality=100",
            "--log=verbose",
            "--gl=angle",
            *self._remotion_quality_flags(width=direction.width, height=direction.height),
        ]

        logger.info("Remotion render command: %s", " ".join(render_cmd))

        total_frames = self._estimate_total_frames(direction)
        remotion_task = asyncio.create_task(
            asyncio.to_thread(
                self._run_remotion_command_streaming,
                job_id=job_id,
                render_cmd=render_cmd,
                remotion_root=remotion_root,
                total_frames=total_frames,
                state=state,
            )
        )

        try:
            return_code, output_lines = await remotion_task
        except asyncio.CancelledError:
            self._terminate_running_process(job_id)
            with contextlib.suppress(BaseException):
                await asyncio.shield(remotion_task)
            raise

        if return_code != 0:
            detail = "\n".join(output_lines[-20:]).strip() or f"Remotion exit code {return_code}"
            logger.error("Remotion render output:\n%s", detail[:2000])
            raise RuntimeError(f"Remotion render failed: {detail[:500]}")

        if not output_path.exists():
            raise RuntimeError(
                f"Remotion render completed but output file not found: {output_path}"
            )

        # Cleanup public dir scene assets after render
        for f in public_dir.glob("scene_*"):
            try:
                f.unlink()
            except OSError:
                pass

        state.progress = 95
        state.detail = "Render complete, finalizing..."
        return output_path

    def _run_remotion_command_streaming(
        self,
        *,
        job_id: str,
        render_cmd: list[str],
        remotion_root: Path,
        total_frames: int,
        state: _JobState,
    ) -> tuple[int, list[str]]:
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        process = subprocess.Popen(
            render_cmd,
            cwd=str(remotion_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            creationflags=creationflags,
        )
        self._render_processes[job_id] = process

        output_lines: list[str] = []
        last_progress = state.progress
        pending_output = ""

        try:
            if process.stdout:
                while True:
                    raw_chunk = process.stdout.read(4096)
                    if not raw_chunk:
                        break
                    pending_output += raw_chunk.decode("utf-8", errors="replace")
                    parts = re.split(r"[\r\n]+", pending_output)
                    pending_output = parts.pop() if parts else ""
                    for line in parts:
                        last_progress = self._consume_remotion_output_line(
                            line=line.strip(),
                            output_lines=output_lines,
                            total_frames=total_frames,
                            state=state,
                            last_progress=last_progress,
                        )

                if pending_output.strip():
                    self._consume_remotion_output_line(
                        line=pending_output.strip(),
                        output_lines=output_lines,
                        total_frames=total_frames,
                        state=state,
                        last_progress=last_progress,
                    )

            return process.wait(), output_lines
        finally:
            with contextlib.suppress(Exception):
                if process.stdout:
                    process.stdout.close()
            self._render_processes.pop(job_id, None)

    def _terminate_running_process(self, job_id: str) -> None:
        process = self._render_processes.get(job_id)
        if process is None or process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _consume_remotion_output_line(
        self,
        *,
        line: str,
        output_lines: list[str],
        total_frames: int,
        state: _JobState,
        last_progress: int,
    ) -> int:
        if not line:
            return last_progress

        output_lines.append(line)
        if len(output_lines) > 80:
            del output_lines[:-80]

        remotion_progress = self._parse_remotion_progress(line, total_frames)
        if remotion_progress is None:
            return last_progress

        mapped_progress = min(95, 68 + round(remotion_progress * 27))
        if mapped_progress <= last_progress:
            return last_progress

        state.progress = mapped_progress
        state.detail = self._build_remotion_progress_detail(
            line,
            remotion_progress,
            total_frames,
        )
        return mapped_progress

    def _estimate_total_frames(self, direction: VideoDirection) -> int:
        fps = max(1, direction.fps)
        current_frame = 0
        last_end_frame = 1
        for scene in direction.scenes:
            scene_frames = max(1, round((scene.total_duration_ms / 1000) * fps))
            last_end_frame = current_frame + scene_frames
            transition_ms = scene.transition_out.duration_ms if scene.transition_out else 0
            overlap = max(0, round((transition_ms / 1000) * fps))
            current_frame += max(1, scene_frames - overlap)
        return max(1, last_end_frame)

    def _parse_remotion_progress(self, line: str, total_frames: int) -> float | None:
        normalized = line.replace("\x1b", "")
        percent_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", normalized)
        if percent_match:
            percent = float(percent_match.group(1))
            if 0 <= percent <= 100:
                return percent / 100

        frame_pair = re.search(r"(\d+)\s*/\s*(\d+)", normalized)
        if frame_pair:
            current = int(frame_pair.group(1))
            total = max(1, int(frame_pair.group(2)))
            return max(0.0, min(1.0, current / total))

        frame_match = re.search(r"(?:frame|rendered)\D+(\d+)", normalized, flags=re.IGNORECASE)
        if frame_match:
            current = int(frame_match.group(1))
            return max(0.0, min(1.0, current / max(1, total_frames)))

        return None

    def _build_remotion_progress_detail(
        self,
        line: str,
        remotion_progress: float,
        total_frames: int,
    ) -> str:
        frame_pair = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if frame_pair:
            return f"Rendering Remotion frame {frame_pair.group(1)}/{frame_pair.group(2)}..."

        frame_match = re.search(r"(?:frame|rendered)\D+(\d+)", line, flags=re.IGNORECASE)
        if frame_match:
            return f"Rendering Remotion frame {frame_match.group(1)}/{total_frames}..."

        return f"Rendering Remotion... {round(remotion_progress * 100)}%"

    def _remotion_quality_flags(self, *, width: int, height: int) -> list[str]:
        crf = "23" if height > width else "21"
        return [
            f"--crf={crf}",
            "--pixel-format=yuv420p",
        ]


class _JobState:
    """Internal mutable job state."""

    def __init__(self, job_id: str, request: VideoProduceRequest) -> None:
        self.job_id = job_id
        self.request = request
        self.phase = VideoJobPhase.queued
        self.progress = 0
        self.detail = "Queued for production"
        self.error: str | None = None
        self.output_path: Path | None = None
        self.tts_result: BatchTtsResult | None = None
        self.direction: VideoDirection | None = None

    def to_status(self) -> VideoJobStatus:
        download_url = None
        if self.phase == VideoJobPhase.completed:
            download_url = f"/api/v1/video/jobs/{self.job_id}/result"

        return VideoJobStatus(
            job_id=self.job_id,
            phase=self.phase,
            progress=self.progress,
            detail=self.detail,
            error=self.error,
            download_url=download_url,
        )
