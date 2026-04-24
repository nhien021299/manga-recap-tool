import numpy as np
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.characters.embedder import CharacterCropEmbedder

def test_embedder():
    embedder = CharacterCropEmbedder(
        Path(".temp"),
        dino_model_path=".models/dinov2",
        embed_device="cpu"
    )
    
    img1 = Image.new("RGB", (200, 200), color="red")
    img2 = Image.new("RGB", (200, 200), color="blue")
    
    vec1 = embedder.embed(chapter_id="1", crop_id="1", crop_kind="face", cache_hint="1", crop_image=img1).vector
    vec2 = embedder.embed(chapter_id="1", crop_id="2", crop_kind="face", cache_hint="1", crop_image=img2).vector
    
    sim = float(np.dot(vec1, vec2))
    print(f"Similarity red vs blue: {sim:.4f}, distance: {1-sim:.4f}")

if __name__ == "__main__":
    test_embedder()
