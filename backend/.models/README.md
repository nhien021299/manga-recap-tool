Place local TTS assets here.

Active providers:

- `vieneu`
  - no checked-in local model bundle is required here
- `f5`
  - ONNX bundles:
    - `backend/.models/f5-onnx/CPU_F32.zip`
    - `backend/.models/f5-onnx/GPU_CUDA_F16.zip`
    - or extracted folders with the same names
  - reference presets:
    - `backend/.models/f5-reference/<preset>.wav`
    - `backend/.models/f5-reference/<preset>.txt`

The backend extracts F5 bundle zip files on first use if the extracted folder is missing.

Runtime diagnostics:

- `GET /api/v1/system/tts?provider=vieneu`
- `GET /api/v1/system/tts?provider=f5`
