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
from app.models.characters import (
    ChapterCharacterState,
    CharacterCandidateAssignment,
    CharacterCluster,
    CharacterCrop,
    CharacterPanelMappingRequest,
    CharacterStatusRequest,
    PanelCharacterRef,
)
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
            prepass_payload = prepass_response.json()
            assert "diagnostics" in prepass_payload
            assert "summary" in prepass_payload["diagnostics"]
            assert "pairs" in prepass_payload["diagnostics"]
            assert "crops" in prepass_payload
            assert "candidateAssignments" in prepass_payload

            create_response = client.post(
                "/api/v1/characters/clusters",
                json={
                    "chapterId": "chapter_test",
                    "canonicalName": "Ly Pham",
                    "displayLabel": "Ly Pham",
                    "lockName": True,
                    "panelIds": ["panel-1"],
                    "cropIds": [],
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


def test_character_split_route_moves_crop_and_rebuilds_script_refs(tmp_path: Path):
    settings = build_route_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    review_service = CharacterReviewStateService(repository)
    script_context_builder = CharacterScriptContextBuilder()
    state = ChapterCharacterState(
        chapterId="chapter_split",
        chapterContentHash="split-hash",
        prepassVersion="character-hybrid-v3",
        generatedAt="2026-04-24T00:00:00+00:00",
        updatedAt="2026-04-24T00:00:00+00:00",
        needsReview=True,
        clusters=[
            CharacterCluster(
                clusterId="char_001",
                chapterId="chapter_split",
                status="locked",
                canonicalName="Ly Pham",
                displayLabel="Ly Pham",
                lockName=True,
                confidenceScore=1.0,
                occurrenceCount=2,
                anchorCropIds=["panel-1::crop::01", "panel-2::crop::01"],
                anchorPanelIds=["panel-1", "panel-2"],
                samplePanelIds=["panel-1", "panel-2"],
            )
        ],
        crops=[
            CharacterCrop(
                cropId="panel-1::crop::01",
                panelId="panel-1",
                orderIndex=0,
                bbox=[0, 0, 20, 20],
                qualityScore=1.0,
                qualityBucket="good",
                assignedClusterId="char_001",
                assignmentState="manual",
            ),
            CharacterCrop(
                cropId="panel-2::crop::01",
                panelId="panel-2",
                orderIndex=1,
                bbox=[0, 0, 20, 20],
                qualityScore=1.0,
                qualityBucket="good",
                assignedClusterId="char_001",
                assignmentState="manual",
            ),
        ],
        panelCharacterRefs=[
            PanelCharacterRef(panelId="panel-1", clusterIds=["char_001"], source="manual", confidenceScore=1.0),
            PanelCharacterRef(panelId="panel-2", clusterIds=["char_001"], source="manual", confidenceScore=1.0),
        ],
    )
    repository.save(state)

    app.dependency_overrides[get_character_review_state_service] = lambda: review_service
    app.dependency_overrides[get_character_script_context_builder] = lambda: script_context_builder

    try:
        with TestClient(app) as client:
            split_response = client.post(
                "/api/v1/characters/split",
                json={
                    "chapterId": "chapter_split",
                    "sourceClusterId": "char_001",
                    "cropIds": ["panel-2::crop::01"],
                    "panelIds": [],
                    "canonicalName": "Minh",
                },
            )
            assert split_response.status_code == 200
            split_payload = split_response.json()
            new_cluster = next(cluster for cluster in split_payload["clusters"] if cluster["canonicalName"] == "Minh")
            moved_crop = next(crop for crop in split_payload["crops"] if crop["cropId"] == "panel-2::crop::01")
            assert moved_crop["assignedClusterId"] == new_cluster["clusterId"]
            assert moved_crop["assignmentState"] == "manual"

            script_context_response = client.get("/api/v1/characters/script-context/chapter_split")
            assert script_context_response.status_code == 200
            script_context = script_context_response.json()
            assert script_context["panelCharacterRefs"]["panel-1"] == ["char_001"]
            assert script_context["panelCharacterRefs"]["panel-2"] == [new_cluster["clusterId"]]
    finally:
        app.dependency_overrides.clear()


def test_manual_panel_override_clears_unresolved_even_with_unknown_crop(tmp_path: Path):
    settings = build_route_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    review_service = CharacterReviewStateService(repository)
    state = ChapterCharacterState(
        chapterId="chapter_manual_override",
        chapterContentHash="manual-hash",
        prepassVersion="character-hybrid-v3",
        generatedAt="2026-04-24T00:00:00+00:00",
        updatedAt="2026-04-24T00:00:00+00:00",
        needsReview=True,
        clusters=[
            CharacterCluster(
                clusterId="char_001",
                chapterId="chapter_manual_override",
                status="locked",
                canonicalName="Ly Pham",
                displayLabel="Ly Pham",
                lockName=True,
            )
        ],
        crops=[
            CharacterCrop(
                cropId="panel-1::crop::01",
                panelId="panel-1",
                orderIndex=0,
                bbox=[0, 0, 20, 20],
                qualityScore=0.7,
                qualityBucket="medium",
                assignedClusterId=None,
                assignmentState="unknown",
            )
        ],
        panelCharacterRefs=[PanelCharacterRef(panelId="panel-1", clusterIds=[], source="unknown", confidenceScore=0.0)],
        unresolvedPanelIds=["panel-1"],
    )
    repository.save(state)

    result = review_service.update_panel_mapping(
        CharacterPanelMappingRequest(chapterId="chapter_manual_override", panelId="panel-1", clusterIds=["char_001"])
    )

    assert "panel-1" not in result.unresolvedPanelIds
    assert result.panelCharacterRefs[0].diagnostics["manualOverride"] is True


def test_unknown_cluster_is_removed_from_refs_and_script_context(tmp_path: Path):
    settings = build_route_settings(tmp_path)
    repository = CharacterStateRepository(settings.character_state_db)
    review_service = CharacterReviewStateService(repository)
    script_context_builder = CharacterScriptContextBuilder()
    state = ChapterCharacterState(
        chapterId="chapter_unknown",
        chapterContentHash="unknown-hash",
        prepassVersion="character-hybrid-v3",
        generatedAt="2026-04-24T00:00:00+00:00",
        updatedAt="2026-04-24T00:00:00+00:00",
        needsReview=False,
        clusters=[
            CharacterCluster(
                clusterId="char_001",
                chapterId="chapter_unknown",
                status="draft",
                canonicalName="",
                displayLabel="nhan vat 1",
            )
        ],
        crops=[
            CharacterCrop(
                cropId="panel-1::crop::01",
                panelId="panel-1",
                orderIndex=0,
                bbox=[0, 0, 20, 20],
                qualityScore=1.0,
                qualityBucket="good",
                assignedClusterId="char_001",
                assignmentState="auto_confirmed",
            )
        ],
        candidateAssignments=[
            CharacterCandidateAssignment(
                cropId="panel-1::crop::01",
                panelId="panel-1",
                clusterId="char_001",
                rank=1,
                score=1.0,
                marginScore=1.0,
                state="auto_confirmed",
            )
        ],
        panelCharacterRefs=[PanelCharacterRef(panelId="panel-1", clusterIds=["char_001"], source="auto_confirmed", confidenceScore=1.0)],
    )
    repository.save(state)

    result = review_service.update_cluster_status(
        CharacterStatusRequest(chapterId="chapter_unknown", clusterId="char_001", status="unknown")
    )
    script_context = script_context_builder.build(result)

    assert result.crops[0].assignedClusterId is None
    assert result.crops[0].assignmentState == "unknown"
    assert result.candidateAssignments == []
    assert result.panelCharacterRefs[0].clusterIds == []
    assert script_context.characters == []
    assert script_context.panelCharacterRefs == {}
    assert script_context.unknownPanelIds == ["panel-1"]
