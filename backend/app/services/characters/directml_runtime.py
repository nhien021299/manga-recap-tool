from __future__ import annotations

from pathlib import Path


def create_onnx_session(model_path: str | Path, *, device: str = "auto"):
    """Create an ONNX Runtime session, preferring DirectML when requested/available."""
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    requested = str(device or "auto").strip().lower()
    providers: list[str] = []
    if requested in {"auto", "gpu", "directml", "dml"} and "DmlExecutionProvider" in available:
        providers.append("DmlExecutionProvider")
    providers.append("CPUExecutionProvider")
    return ort.InferenceSession(str(model_path), providers=providers)


def session_diagnostics(session) -> dict[str, object]:
    try:
        return {
            "providers": list(session.get_providers()),
            "inputNames": [item.name for item in session.get_inputs()],
            "outputNames": [item.name for item in session.get_outputs()],
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
