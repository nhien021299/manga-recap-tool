from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _normalize_secret(value: str | None) -> str:
    if not value:
        return ""
    trimmed = value.strip()
    if not trimmed:
        return ""
    if (
        (trimmed.startswith('"') and trimmed.endswith('"'))
        or (trimmed.startswith("'") and trimmed.endswith("'"))
    ):
        return trimmed[1:-1].strip()
    return trimmed


def _resolve_backend_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (BACKEND_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", alias="AI_BACKEND_HOST")
    port: int = Field(default=8000, alias="AI_BACKEND_PORT")
    api_prefix: str = "/api/v1"
    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
        alias="AI_BACKEND_CORS_ORIGINS",
    )
    temp_root_raw: str = Field(default=".temp/jobs", alias="AI_BACKEND_TEMP_ROOT")
    render_temp_root_raw: str = Field(default=".temp/render-jobs", alias="AI_BACKEND_RENDER_TEMP_ROOT")
    render_ffmpeg_path: str = Field(default="ffmpeg", alias="AI_BACKEND_RENDER_FFMPEG_PATH")
    render_result_ttl_seconds: int = Field(default=3600, alias="AI_BACKEND_RENDER_RESULT_TTL_SECONDS")
    gemini_api_key: str = Field(default="", alias="AI_BACKEND_GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="AI_BACKEND_GEMINI_MODEL")
    gemini_api_endpoint: str | None = Field(default=None, alias="AI_BACKEND_GEMINI_API_ENDPOINT")
    gemini_script_batch_size: int = Field(default=4, alias="AI_BACKEND_GEMINI_SCRIPT_BATCH_SIZE")
    gemini_max_concurrent_requests: int = Field(default=1, alias="AI_BACKEND_GEMINI_MAX_CONCURRENT_REQUESTS")
    gemini_min_request_interval_ms: int = Field(default=750, alias="AI_BACKEND_GEMINI_MIN_REQUEST_INTERVAL_MS")
    gemini_retry_attempts: int = Field(default=4, alias="AI_BACKEND_GEMINI_RETRY_ATTEMPTS")
    gemini_retry_base_delay_ms: int = Field(default=2000, alias="AI_BACKEND_GEMINI_RETRY_BASE_DELAY_MS")
    gemini_retry_max_delay_ms: int = Field(default=15000, alias="AI_BACKEND_GEMINI_RETRY_MAX_DELAY_MS")
    gemini_cooldown_on_429_ms: int = Field(default=20000, alias="AI_BACKEND_GEMINI_COOLDOWN_ON_429_MS")
    vision_max_width: int = Field(default=512, alias="AI_BACKEND_VISION_MAX_WIDTH")
    vision_max_height: int = Field(default=1024, alias="AI_BACKEND_VISION_MAX_HEIGHT")
    tts_provider: str = Field(default="vietvoice", alias="AI_BACKEND_TTS_PROVIDER")
    tts_runtime: str = Field(default="directml", alias="AI_BACKEND_TTS_RUNTIME")
    tts_warm_on_startup: bool = Field(default=False, alias="AI_BACKEND_TTS_WARM_ON_STARTUP")
    tts_smoke_test_text: str = Field(default="", alias="AI_BACKEND_TTS_SMOKE_TEST_TEXT")
    tts_max_concurrent_jobs: int = Field(default=1, alias="AI_BACKEND_TTS_MAX_CONCURRENT_JOBS")


    @field_validator("tts_runtime", mode="before")
    @classmethod
    def _normalize_tts_runtime(cls, value: object) -> str:
        if value is None:
            return "directml"
        normalized = str(value).strip().lower()
        if normalized in {"", "auto", "cpu", "gpu", "directml"}:
            return normalized or "directml"
        raise ValueError("AI_BACKEND_TTS_RUNTIME must be one of: auto, cpu, gpu, directml.")

    @field_validator("tts_max_concurrent_jobs", mode="before")
    @classmethod
    def _normalize_tts_max_concurrent_jobs(cls, value: object) -> int:
        if value is None:
            return 1
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("AI_BACKEND_TTS_MAX_CONCURRENT_JOBS must be an integer.") from exc
        return max(1, parsed)

    @field_validator("tts_provider", mode="before")
    @classmethod
    def _normalize_tts_provider(cls, value: object) -> str:
        if value is None:
            return "vietvoice"
        normalized = str(value).strip().lower()
        if normalized in {"", "vietvoice"}:
            return normalized or "vietvoice"
        raise ValueError("AI_BACKEND_TTS_PROVIDER must be 'vietvoice'.")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def temp_root(self) -> Path:
        return _resolve_backend_path(self.temp_root_raw)

    @property
    def render_temp_root(self) -> Path:
        return _resolve_backend_path(self.render_temp_root_raw)



    @property
    def effective_gemini_api_key(self) -> str:
        return _normalize_secret(self.gemini_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
