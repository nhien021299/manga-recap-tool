from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.deps import get_app_settings, get_voice_service
from app.main import app
from app.models.api import (
    VoiceGenerateRequest,
    VoiceOption,
    VoiceOptionsResponse,
    VoiceProviderOption,
)
from app.services.voice_service import VoiceService


class DummyVoiceProvider:
    provider_id = "vieneu"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def get_options(self) -> VoiceProviderOption:
        return VoiceProviderOption(
            id="vieneu",
            label="VieNeu V2 Turbo",
            enabled=self.enabled,
            defaultVoiceKey="default",
            statusMessage=None if self.enabled else "missing assets",
            voices=[
                VoiceOption(
                    key="default",
                    label="Default",
                    provider="vieneu",
                    isAvailable=self.enabled,
                )
            ],
        )

    def generate_audio(self, request: VoiceGenerateRequest) -> bytes:
        if not request.text.strip():
            raise ValueError("Voice generation text cannot be empty.")
        return b"RIFFdemoWAVE"


def build_voice_settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None).model_copy(
        update={
            "temp_root_raw": str(tmp_path / ".temp" / "jobs"),
        }
    )


def test_voice_options_route_returns_provider_payload(tmp_path: Path):
    settings = build_voice_settings(tmp_path)
    voice_service = VoiceService("vieneu", {"vieneu": DummyVoiceProvider()})
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_voice_service] = lambda: voice_service

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/voice/options")
        assert response.status_code == 200
        payload = VoiceOptionsResponse(**response.json())
        assert payload.defaultProvider == "vieneu"
        assert payload.providers[0].voices[0].key == "default"
    finally:
        app.dependency_overrides.clear()


def test_voice_generate_route_returns_wav_bytes(tmp_path: Path):
    settings = build_voice_settings(tmp_path)
    voice_service = VoiceService("vieneu", {"vieneu": DummyVoiceProvider()})
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_voice_service] = lambda: voice_service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/voice/generate",
                json={
                    "text": "Xin chao",
                    "provider": "vieneu",
                    "voiceKey": "default",
                },
            )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("audio/wav")
        assert response.content.startswith(b"RIFF")
    finally:
        app.dependency_overrides.clear()


def test_voice_generate_route_rejects_empty_text(tmp_path: Path):
    settings = build_voice_settings(tmp_path)
    voice_service = VoiceService("vieneu", {"vieneu": DummyVoiceProvider()})
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_voice_service] = lambda: voice_service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/voice/generate",
                json={
                    "text": "   ",
                    "provider": "vieneu",
                    "voiceKey": "default",
                },
            )
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_voice_generate_route_returns_missing_asset_error(tmp_path: Path):
    settings = build_voice_settings(tmp_path)
    voice_service = VoiceService("vieneu", {"vieneu": DummyVoiceProvider(enabled=False)})
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_voice_service] = lambda: voice_service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/voice/generate",
                json={
                    "text": "Xin chao",
                    "provider": "vieneu",
                    "voiceKey": "default",
                },
            )
        assert response.status_code == 500
        assert "missing assets" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
