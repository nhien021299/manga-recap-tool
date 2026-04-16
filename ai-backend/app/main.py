from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.routes.caption import router as caption_router
from app.routes.health import router as health_router
from app.routes.script import router as script_router
from app.routes.system import router as system_router
from app.services.caption_service import CaptionService
from app.services.gemini_script_service import GeminiScriptService
from app.services.job_queue import JobQueue
from app.services.llm_service import LLMService
from app.services.provider_registry import ProviderRegistry
from app.services.script_pipeline import ScriptPipeline


def build_services(settings: Settings) -> dict[str, object]:
    provider_registry = ProviderRegistry(settings)
    text_provider = provider_registry.get_text_provider()
    vision_provider = provider_registry.get_vision_provider()
    ocr_provider = provider_registry.get_ocr_provider()
    caption_service = CaptionService(settings, vision_provider, text_provider, ocr_provider=ocr_provider)
    llm_service = LLMService(settings, text_provider)
    script_pipeline = ScriptPipeline(provider_registry, caption_service, llm_service)
    job_queue = JobQueue(script_pipeline)
    gemini_script_service = GeminiScriptService(settings)
    return {
        "provider_registry": provider_registry,
        "caption_service": caption_service,
        "job_queue": job_queue,
        "gemini_script_service": gemini_script_service,
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


app = FastAPI(title="manga-recap-tool ai-backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
prefix = get_settings().api_prefix
app.include_router(health_router, prefix=prefix)
app.include_router(system_router, prefix=prefix)
app.include_router(caption_router, prefix=prefix)
app.include_router(script_router, prefix=prefix)
