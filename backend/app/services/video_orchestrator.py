"""Video production orchestrator.

Coordinates the full pipeline: TTS → Gemini direction → Remotion render.
Manages job state and progress tracking.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from app.core.config import Settings
from app.models.video import (
    BatchTtsRequest,
    BatchTtsResult,
    NarrationPackage,
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

    def _video_jobs_root(self) -> Path:
        return self.settings.render_temp_root.parent / "video-jobs"

    async def start_production(self, request: VideoProduceRequest) -> VideoJobStatus:
        """Start a video production job. Returns immediately with job ID."""
        job_id = str(uuid.uuid4())
        state = _JobState(job_id=job_id, request=request)
        self._jobs[job_id] = state

        # Run the pipeline in background
        asyncio.create_task(self._run_pipeline(state))

        return state.to_status()

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

    async def _run_pipeline(self, state: _JobState) -> None:
        """Execute the full production pipeline."""
        request = state.request
        job_id = state.job_id

        try:
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

            tts_result: BatchTtsResult = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.video_tts_service.generate_batch(
                    tts_request, job_id=job_id
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

            package = self.video_tts_service.parse_narration_file(
                request.narration_path
            )

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
        import subprocess

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
            "--log=verbose",
        ]

        logger.info("Remotion render command: %s", " ".join(render_cmd))

        def run_remotion():
            return subprocess.run(
                render_cmd,
                cwd=str(remotion_root),
                capture_output=True,
            )

        process = await asyncio.to_thread(run_remotion)

        if process.returncode != 0:
            stderr_text = process.stderr.decode("utf-8", errors="replace").strip()
            stdout_text = process.stdout.decode("utf-8", errors="replace").strip()
            detail = stderr_text or stdout_text or f"Remotion exit code {process.returncode}"
            logger.error("Remotion render stderr:\n%s", detail[:2000])
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
