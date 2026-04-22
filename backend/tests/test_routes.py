import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.deps import get_app_settings, get_gemini_script_service
from app.main import app, build_services
from app.models.api import ScriptJobResult
from app.models.domain import Metrics, RawOutputs


def test_healthcheck():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_providers_route_includes_ocr_fields(monkeypatch):
    monkeypatch.setenv("AI_BACKEND_OCR_ENABLED", "true")
    get_settings.cache_clear()

    from app.services.provider_registry import ProviderRegistry

    monkeypatch.setattr(ProviderRegistry, "get_ocr_provider", lambda self: None)
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/system/providers")
            assert response.status_code == 200
            payload = response.json()
            assert payload["ocrEnabled"] is True
            assert payload["ocrProvider"] == "paddleocr"
    finally:
        get_settings.cache_clear()


def test_tts_runtime_route_returns_runtime_payload():
    with TestClient(app) as client:
        response = client.get("/api/v1/system/tts")
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "vieneu"
        assert payload["resolvedRuntime"] in {"cpu", "gpu"}
        assert payload["executionProvider"] in {"torch-cpu", "torch-gpu"}
        assert "deviceName" in payload
        assert payload["modelBundle"] == "pnnbao-ump/VieNeu-TTS-0.3B"
        assert payload["runtimePython"]

def test_tts_runtime_route_accepts_explicit_vieneu_provider():
    with TestClient(app) as client:
        response = client.get("/api/v1/system/tts", params={"provider": "vieneu"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "vieneu"


def test_voice_sample_assets_allow_cross_origin_embedding():
    with TestClient(app) as client:
        response = client.get("/assets/voice-samples/vieneu/voice-default.wav")

    assert response.status_code == 200
    assert response.headers["cross-origin-resource-policy"] == "cross-origin"


def test_tts_runtime_route_rejects_unknown_provider():
    with TestClient(app) as client:
        response = client.get("/api/v1/system/tts", params={"provider": "legacy"})
        assert response.status_code == 404
        assert "Unsupported TTS provider" in response.json()["detail"]


class DummyGeminiService:
    def __init__(self, result: ScriptJobResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def generate_script(self, **_kwargs):
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def build_route_settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None).model_copy(
        update={
            "temp_root_raw": str(tmp_path / ".temp" / "jobs"),
            "gemini_api_key": "test-key",
        }
    )


def test_script_generate_route_returns_metrics_and_result(tmp_path: Path):
    settings = build_route_settings(tmp_path)
    result = ScriptJobResult(
        understandings=[],
        generatedItems=[],
        storyMemories=[],
        panelSignature="sig",
        rawOutputs=RawOutputs(script="[]"),
        metrics=Metrics(
            panelCount=1,
            totalMs=100,
            captionMs=0,
            scriptMs=100,
            batchSizeUsed=4,
            retryCount=1,
            rateLimitedCount=0,
            throttleWaitMs=750,
            identityOcrMs=0,
            identityConfirmedCount=0,
        ),
    )
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_gemini_script_service] = lambda: DummyGeminiService(result=result)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/script/generate",
                data={
                    "context": json.dumps({"language": "vi"}),
                    "panels": json.dumps([{"panelId": "p1", "orderIndex": 0}]),
                    "options": json.dumps({"returnRawOutputs": True}),
                },
                files=[("files", ("panel-1.png", b"fake-image-bytes", "image/png"))],
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["error"] is None
        assert payload["result"]["metrics"]["batchSizeUsed"] == 4
        assert payload["result"]["metrics"]["retryCount"] == 1
        assert payload["result"]["metrics"]["throttleWaitMs"] == 750
    finally:
        app.dependency_overrides.clear()


def test_script_generate_route_returns_error_body_with_logs(tmp_path: Path):
    settings = build_route_settings(tmp_path)
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_gemini_script_service] = lambda: DummyGeminiService(error=RuntimeError("boom"))

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/script/generate",
                data={
                    "context": json.dumps({"language": "vi"}),
                    "panels": json.dumps([{"panelId": "p1", "orderIndex": 0}]),
                },
                files=[("files", ("panel-1.png", b"fake-image-bytes", "image/png"))],
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["result"] is None
        assert payload["error"] == "boom"
        assert any(log["type"] == "error" for log in payload["logs"])
    finally:
        app.dependency_overrides.clear()


def test_build_services_shares_gate_between_sync_and_queue():
    settings = Settings(_env_file=None).model_copy(update={"gemini_api_key": "test-key"})
    services = build_services(settings)

    assert services["job_queue"].script_pipeline is services["gemini_script_service"]
    assert services["gemini_script_service"].gemini_request_gate is services["gemini_request_gate"]
