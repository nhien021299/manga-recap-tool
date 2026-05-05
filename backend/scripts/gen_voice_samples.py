import sys
import os
import io
from pathlib import Path

# Force UTF-8 for console output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.tts.vietvoice.vietvoice_provider import get_vietvoice_service

def generate_samples():
    service = get_vietvoice_service()
    
    # Text from frontend StepVoice.tsx PREVIEW_TEXT
    text = "Xin chào, đây là đoạn nghe thử để kiểm tra chất giọng kể chuyện, độ cuốn và nhịp review truyện của preset này."
    
    samples_dir = Path("d:/code/manhwa-recap-tool/backend/.bench/samples")
    samples_dir.mkdir(parents=True, exist_ok=True)
    
    voices = ["lat_radio"]
    
    for voice in voices:
        print(f"--- Generating sample for {voice} ---")
        try:
            # The synthesize method will handle reference loading.
            # If it fails due to duration, we might need to manually trim it first,
            # but let's see if we can just call it with the existing voice.
            
            output_path = service.synthesize(
                text=text,
                output_name=f"{voice}.wav",
                voice_key=voice,
                job_id=f"sample_gen_{voice}_v4",
                speed=1.0
            )
            
            # Move/copy to target location
            target_path = samples_dir / f"{voice}.wav"
            if target_path.exists():
                target_path.unlink()
            
            import shutil
            shutil.copy(str(output_path), str(target_path))
            print(f"Success: {target_path}")
        except Exception as e:
            print(f"Failed to generate {voice}: {e}")

if __name__ == "__main__":
    generate_samples()
