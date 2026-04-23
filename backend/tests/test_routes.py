import json
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings, get_settings
from app.deps import (
    get_app_settings,
    get_character_prepass_service,
    get_character_review_state_service,
    get_character_script_context_builder,
    get_gemini_script_service,
)
from app.main import app, build_services
from app.models.api import ScriptJobResult
from app.models.domain import Metrics, RawOutputs
from app.services.characters.prepass import CharacterPrepassService
from app.services.characters.repository import CharacterStateRepository
from app.services.characters.review_state import CharacterReviewStateService
from app.services.characters.script_context import CharacterScriptContextBuilder


def test_healthcheck():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"




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


def build_test_png(color: int = 255) -> bytes:
    image = Image.new("L", (32, 48), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_route_settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None).model_copy(
        update={
            "temp_root_raw": str(tmp_path / ".temp" / "jobs"),
            "character_state_db_raw": str(tmp_path / ".temp" / "characters" / "state.sqlite3"),
            "character_cache_root_raw": str(tmp_path / ".temp" / "characters" / "cache"),
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


def test_script_generate_get_returns_actionable_method_error():
    with TestClient(app) as client:
        response = client.get("/api/v1/script/generate")

    assert response.status_code == 405
    assert "Use POST /api/v1/script/generate" in response.json()["detail"]


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


def test_character_routes_support_prepass_review_and_script_context(tmp_path: Path):
    settings = build_route_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    review_service = CharacterReviewStateService(repository)
    prepass_service = CharacterPrepassService(settings, repository)
    script_context_builder = CharacterScriptContextBuilder()

    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_character_prepass_service] = lambda: prepass_service
    app.dependency_overrides[get_character_review_state_service] = lambda: review_service
    app.dependency_overrides[get_character_script_context_builder] = lambda: script_context_builder

    try:
        with TestClient(app) as client:
            prepass_response = client.post(
                "/api/v1/characters/prepass",
                data={
                    "payload": json.dumps(
                        {
                            "chapterId": "chapter_test",
                            "panels": [
                                {"panelId": "panel-1", "orderIndex": 0},
                                {"panelId": "panel-2", "orderIndex": 1},
                            ],
                        }
                    )
                },
                files=[
                    ("files", ("panel-1.png", build_test_png(255), "image/png")),
                    ("files", ("panel-2.png", build_test_png(220), "image/png")),
                ],
            )
            assert prepass_response.status_code == 200

            create_response = client.post(
                "/api/v1/characters/clusters",
                json={
                    "chapterId": "chapter_test",
                    "canonicalName": "Ly Pham",
                    "displayLabel": "Ly Pham",
                    "lockName": True,
                    "panelIds": ["panel-1"],
                },
            )
            assert create_response.status_code == 200
            create_payload = create_response.json()
            cluster_id = create_payload["clusters"][-1]["clusterId"]

            mapping_response = client.post(
                "/api/v1/characters/panel-mapping",
                json={
                    "chapterId": "chapter_test",
                    "panelId": "panel-2",
                    "clusterIds": [cluster_id],
                },
            )
            assert mapping_response.status_code == 200

            script_context_response = client.get("/api/v1/characters/script-context/chapter_test")
            assert script_context_response.status_code == 200
            script_context = script_context_response.json()
            assert script_context["chapterId"] == "chapter_test"
            assert script_context["characters"][0]["canonicalName"] == "Ly Pham"
            assert script_context["panelCharacterRefs"]["panel-1"] == [cluster_id]
            assert script_context["panelCharacterRefs"]["panel-2"] == [cluster_id]
    finally:
        app.dependency_overrides.clear()
