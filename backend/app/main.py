from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.routes.caption import router as caption_router
from app.routes.health import router as health_router
from app.routes.script import router as script_router
from app.routes.system import router as system_router
from app.routes.voice import router as voice_router
from app.services.caption_service import CaptionService
from app.services.gemini_script_service import GeminiScriptService
from app.services.gemini_request_gate import GeminiRequestGate
from app.services.job_queue import JobQueue
from app.services.llm_service import LLMService
from app.services.provider_registry import ProviderRegistry
from app.services.script_pipeline import ScriptPipeline
from app.services.voice_service import VoiceService


def build_services(settings: Settings) -> dict[str, object]:
    provider_registry = ProviderRegistry(settings)
    text_provider = provider_registry.get_text_provider()
    vision_provider = provider_registry.get_vision_provider()
    ocr_provider = provider_registry.get_ocr_provider()
    identity_ocr_provider = provider_registry.get_identity_ocr_provider()
    caption_service = CaptionService(settings, vision_provider, text_provider, ocr_provider=ocr_provider)
    llm_service = LLMService(settings, text_provider)
    script_pipeline = ScriptPipeline(provider_registry, caption_service, llm_service)
    tts_providers = provider_registry.get_tts_providers()
    provider_registry.warm_tts_runtime()
    voice_service = VoiceService(settings.tts_provider, tts_providers)
    gemini_request_gate = GeminiRequestGate(
        max_concurrent_requests=settings.gemini_max_concurrent_requests,
        min_request_interval_ms=settings.gemini_min_request_interval_ms,
        cooldown_on_429_ms=settings.gemini_cooldown_on_429_ms,
    )
    gemini_script_service = GeminiScriptService(
        settings,
        identity_ocr_provider=identity_ocr_provider,
        gemini_request_gate=gemini_request_gate,
    )
    job_queue = JobQueue(gemini_script_service)
    return {
        "provider_registry": provider_registry,
        "caption_service": caption_service,
        "job_queue": job_queue,
        "gemini_script_service": gemini_script_service,
        "gemini_request_gate": gemini_request_gate,
        "voice_service": voice_service,
        "tts_runtime": provider_registry.get_default_tts_runtime(),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    settings.temp_root.mkdir(parents=True, exist_ok=True)
    services = build_services(settings)
    app.state.settings = settings
    for key, value in services.items():
        setattr(app.state, key, value)
    await app.state.job_queue.start()
    try:
        yield
    finally:
        await app.state.job_queue.stop()


app = FastAPI(title="manga-recap-tool backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_static_asset_embed_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/assets/voice-samples/"):
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response


prefix = get_settings().api_prefix
app.include_router(health_router, prefix=prefix)
app.include_router(system_router, prefix=prefix)
app.include_router(caption_router, prefix=prefix)
app.include_router(script_router, prefix=prefix)
app.include_router(voice_router, prefix=prefix)

voice_samples_dir = Path(__file__).resolve().parents[1] / ".bench" / "samples"
voice_samples_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets/voice-samples", StaticFiles(directory=str(voice_samples_dir)), name="voice-samples")
