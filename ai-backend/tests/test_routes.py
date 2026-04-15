from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_healthcheck():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_providers_route_includes_ocr_fields(monkeypatch):
    monkeypatch.setenv("AI_BACKEND_OCR_ENABLED", "true")
    monkeypatch.setenv("AI_BACKEND_OCR_PROVIDER", "rapidocr")
    get_settings.cache_clear()

    from app.services.provider_registry import ProviderRegistry

    monkeypatch.setattr(ProviderRegistry, "get_ocr_provider", lambda self: None)
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/system/providers")
            assert response.status_code == 200
            payload = response.json()
            assert payload["ocrEnabled"] is True
            assert payload["ocrProvider"] == "rapidocr"
    finally:
        get_settings.cache_clear()
