from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .vietvoice_config import VietVoiceConfig
from .vietvoice_service import VietVoiceService


@lru_cache(maxsize=1)
def get_vietvoice_service() -> VietVoiceService:
    # backend/app/services/tts/vietvoice/vietvoice_provider.py
    # So parents[4] is backend
    backend_root = Path(__file__).resolve().parents[4]
    config = VietVoiceConfig.from_env(backend_root)
    return VietVoiceService(config)
