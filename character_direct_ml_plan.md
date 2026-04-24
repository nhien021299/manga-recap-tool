📄 CHARACTER SYSTEM – ONNX DIRECTML INTEGRATION PLAN
🎯 Goal
Tận dụng GPU AMD (RX 6800XT) bằng onnxruntime-directml
Tăng tốc pipeline character system x3–x6
KHÔNG làm giảm quality (tránh bug cluster hiện tại)
Giữ pipeline nhẹ, không phình complexity
🧠 1. Kiến trúc tổng thể
Scene Images
   ↓
[Face/Head Detection - ONNX + DirectML]   🔥 GPU
   ↓
[Crop Quality Filter - CPU]
   ↓
[Crop Type Classifier - (Optional DML)]
   ↓
[Face Embedding (ArcFace) - ONNX + DML]   🔥 GPU
   ↓
[Clustering (HDBSCAN) - CPU]
   ↓
[Outlier Reject + Split - CPU]
   ↓
[UI Character Review]
⚙️ 2. Module Structure (apply vào repo của bạn)
backend/
  character/
    inference/
      dml_runtime.py
      face_detector.py
      face_embedding.py
      crop_classifier.py
    pipeline/
      character_pipeline.py
    clustering/
      cluster_engine.py
⚡ 3. Setup ONNX Runtime DirectML
Install
pip install onnxruntime-directml
Runtime Wrapper
dml_runtime.py
import onnxruntime as ort

def create_dml_session(model_path):
    return ort.InferenceSession(
        model_path,
        providers=["DmlExecutionProvider"]
    )
🧬 4. Face Detection (GPU)
Model đề xuất
retinaface.onnx (ưu tiên)
hoặc scrfd_500m.onnx (nhẹ hơn)
face_detector.py
import cv2
import numpy as np
from .dml_runtime import create_dml_session

class FaceDetector:
    def __init__(self, model_path):
        self.session = create_dml_session(model_path)

    def detect(self, image):
        input_img = self.preprocess(image)
        outputs = self.session.run(None, {"input": input_img})
        return self.postprocess(outputs)

    def preprocess(self, img):
        img = cv2.resize(img, (640, 640))
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        return np.expand_dims(img, axis=0)

    def postprocess(self, outputs):
        # TODO: decode bbox
        return outputs
🧠 5. Face Embedding (QUAN TRỌNG NHẤT)
Model

👉 ArcFace ONNX (buffalo_l)

❌ KHÔNG dùng CLIP
❌ KHÔNG dùng full image embedding

face_embedding.py
import numpy as np
from .dml_runtime import create_dml_session

class FaceEmbedder:
    def __init__(self, model_path):
        self.session = create_dml_session(model_path)

    def embed(self, face_crop):
        input_data = self.preprocess(face_crop)
        embedding = self.session.run(None, {"input": input_data})[0]
        return self.normalize(embedding)

    def preprocess(self, img):
        img = cv2.resize(img, (112, 112))
        img = img.astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        img = np.transpose(img, (2, 0, 1))
        return np.expand_dims(img, axis=0)

    def normalize(self, emb):
        return emb / np.linalg.norm(emb)
🧪 6. Crop Type Classifier (OPTIONAL)

Phân loại:

face / head / body / monster / unknown

👉 Có thể chạy CPU hoặc DirectML đều OK

🚫 7. Những thứ KHÔNG dùng DirectML
Component	Lý do
Clustering	CPU faster
Rule filtering	logic
HDBSCAN	không benefit GPU
Prompt generation	irrelevant
🔥 8. Batch Optimization (QUAN TRỌNG)
Sai lầm:
for crop in crops:
    embed(crop)
Đúng:
batch = np.stack(crops)
embeddings = session.run(None, {"input": batch})

👉 Tăng tốc cực mạnh trên GPU

💾 9. Embedding Cache
Tránh compute lại:
cache = {}

def get_embedding(image_id, crop):
    if image_id in cache:
        return cache[image_id]

    emb = embedder.embed(crop)
    cache[image_id] = emb
    return emb
🧹 10. Quality Gate (fix bug hiện tại của bạn)
if crop.type not in ["face", "head"]:
    skip

if crop.quality < 0.55:
    skip
⚠️ 11. Critical Fix (liên quan bug của bạn)
BẮT BUỘC:
allow_body_for_identity = False
allow_monster_for_identity = False
Outlier reject:
if distance(crop, cluster_center) > 0.30:
    move_to_unknown
📊 12. Benchmark mục tiêu
Stage	CPU	DirectML
Detection	200ms	~40ms
Embedding	50ms	~10ms

👉 Tổng pipeline giảm từ ~8s → ~2–3s

🧪 13. Debug Mode
print("DML Providers:", session.get_providers())

Expected:

['DmlExecutionProvider']
🚀 14. Integration vào repo bạn
Thay thế:
anime-face-detector → ONNX RetinaFace
embedding hiện tại → ArcFace ONNX
Giữ nguyên:
clustering logic (nhưng fix threshold)
UI character grouping
🎯 15. Final Checklist
 Face detection chạy DML
 Embedding dùng ArcFace (DML)
 Không dùng CLIP
 Batch inference
 Có cache embedding
 Reject crop bẩn
 Không cho body vào cluster
 Outlier filter sau cluster
🧠 Câu chốt

GPU sẽ biến pipeline của bạn thành Ferrari
Nhưng phải đảm bảo bạn đang lái đúng đường, không phải lao xuống vực nhanh hơn.