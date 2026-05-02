import asyncio
import uuid
from pathlib import Path
import json

from app.core.config import get_settings
from app.models.video import NarrationPackage, BatchTtsResult, SceneTtsResult
from app.services.video_director_service import VideoDirectorService
from app.services.video_orchestrator import VideoOrchestrator, _JobState
from app.services.gemini_request_gate import GeminiRequestGate

async def main():
    print("Loading package...")
    settings = get_settings()
    pkg_path = Path(r"D:\AI\Resources\chapter_2\chapter_2_narration_tts.json")
    pkg = NarrationPackage(**json.loads(pkg_path.read_text(encoding="utf-8")))
    
    job_id = str(uuid.uuid4())
    print(f"Starting mock job: {job_id}")
    
    print("Mocking TTS results...")
    scene_results = []
    # Just mock a 3-second audio for each scene to make it super fast
    for s in pkg.scenes:
        scene_results.append(SceneTtsResult(
            scene=s.scene,
            title=s.title,
            narration=s.narration,
            target_duration_ms=s.duration_seconds * 1000,
            audio_path=str(Path(r"D:\AI\Resources\chapter_2") / "dummy.wav"), # We won't actually copy this if it doesn't exist, which is fine
            audio_duration_ms=3000,
            dialogue_audio_path=None,
            dialogue_duration_ms=None
        ))
    
    tts_result = BatchTtsResult(
        total_scenes=len(pkg.scenes),
        total_audio_duration_ms=3000 * len(pkg.scenes),
        scene_results=scene_results
    )
    
    print("Initializing services...")
    gate = GeminiRequestGate()
    director = VideoDirectorService(settings, gemini_request_gate=gate)
    orchestrator = VideoOrchestrator(settings, video_tts_service=None, video_director_service=director)
    
    state = _JobState(job_id=job_id, request=None)
    
    print("Running Gemini Director...")
    try:
        direction = await director.generate_direction(
            package=pkg,
            tts_result=tts_result,
            job_id=job_id,
            width=1920,
            height=1080,
            fps=30
        )
    except Exception as e:
        print(f"Gemini error: {e}")
        return
        
    print(f"Director finished. Total duration: {direction.total_duration_ms}ms")
    
    print("Starting Remotion Render...")
    try:
        out_path = await orchestrator._render_with_remotion(
            job_id=job_id,
            package=pkg,
            tts_result=tts_result,
            direction=direction,
            state=state
        )
        print(f"DONE! Output is at: {out_path}")
    except Exception as e:
        print(f"Render error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
