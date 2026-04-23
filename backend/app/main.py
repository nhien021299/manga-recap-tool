from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.routes.characters import router as character_router
from app.routes.health import router as health_router
from app.routes.render import router as render_router
from app.routes.script import router as script_router
from app.routes.system import router as system_router
from app.routes.voice import router as voice_router
from app.services.characters.prepass import CharacterPrepassService
from app.services.characters.repository import CharacterStateRepository
from app.services.characters.review_state import CharacterReviewStateService
from app.services.characters.script_context import CharacterScriptContextBuilder
from app.services.gemini_script_service import GeminiScriptService
from app.services.gemini_request_gate import GeminiRequestGate
from app.services.job_queue import JobQueue

from app.services.provider_registry import ProviderRegistry
from app.services.render_queue import RenderJobQueue
from app.services.render_service import NativeFfmpegRenderService
from app.services.voice_service import VoiceService


def build_services(settings: Settings) -> dict[str, object]:
    provider_registry = ProviderRegistry(settings)
    character_repository = CharacterStateRepository(settings.character_state_db)
    character_review_state_service = CharacterReviewStateService(character_repository)
    character_prepass_service = CharacterPrepassService(settings, character_repository)
    character_script_context_builder = CharacterScriptContextBuilder()

    tts_providers = provider_registry.get_tts_providers()
    provider_registry.warm_tts_runtime()
    voice_service = VoiceService(settings.tts_provider, tts_providers)
    render_service = NativeFfmpegRenderService(settings)
    render_queue = RenderJobQueue(render_service)
    gemini_request_gate = GeminiRequestGate(
        max_concurrent_requests=settings.gemini_max_concurrent_requests,
        min_request_interval_ms=settings.gemini_min_request_interval_ms,
        cooldown_on_429_ms=settings.gemini_cooldown_on_429_ms,
    )
    gemini_script_service = GeminiScriptService(
        settings,
        gemini_request_gate=gemini_request_gate,
    )
    job_queue = JobQueue(gemini_script_service)
    return {
        "provider_registry": provider_registry,
        "character_review_state_service": character_review_state_service,
        "character_prepass_service": character_prepass_service,
        "character_script_context_builder": character_script_context_builder,
        "job_queue": job_queue,
        "gemini_script_service": gemini_script_service,
        "gemini_request_gate": gemini_request_gate,
        "voice_service": voice_service,
        "tts_runtime": provider_registry.get_default_tts_runtime(),
        "render_service": render_service,
        "render_queue": render_queue,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    settings.temp_root.mkdir(parents=True, exist_ok=True)
    settings.character_state_db.parent.mkdir(parents=True, exist_ok=True)
    settings.character_cache_root.mkdir(parents=True, exist_ok=True)
    settings.render_temp_root.mkdir(parents=True, exist_ok=True)
    services = build_services(settings)
    app.state.settings = settings
    for key, value in services.items():
        setattr(app.state, key, value)
    await app.state.job_queue.start()
    await app.state.render_queue.start()
    try:
        yield
    finally:
        await app.state.render_queue.stop()
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
app.include_router(character_router, prefix=prefix)
app.include_router(script_router, prefix=prefix)
app.include_router(voice_router, prefix=prefix)
app.include_router(render_router, prefix=prefix)

voice_samples_dir = Path(__file__).resolve().parents[1] / ".bench" / "samples"
voice_samples_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets/voice-samples", StaticFiles(directory=str(voice_samples_dir)), name="voice-samples")
