from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    gemini_api_key: str = Field(default="", alias="AI_BACKEND_GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="AI_BACKEND_GEMINI_MODEL")
    gemini_api_endpoint: str | None = Field(default=None, alias="AI_BACKEND_GEMINI_API_ENDPOINT")
    gemini_script_batch_size: int = Field(default=4, alias="AI_BACKEND_GEMINI_SCRIPT_BATCH_SIZE")
    gemini_identity_experiment_enabled: bool = Field(
        default=True,
        alias="AI_BACKEND_GEMINI_IDENTITY_EXPERIMENT_ENABLED",
    )
    gemini_identity_ocr_min_confidence: float = Field(
        default=0.70,
        alias="AI_BACKEND_GEMINI_IDENTITY_OCR_MIN_CONFIDENCE",
    )
    gemini_identity_ocr_max_text_lines: int = Field(
        default=8,
        alias="AI_BACKEND_GEMINI_IDENTITY_OCR_MAX_TEXT_LINES",
    )
    gemini_max_concurrent_requests: int = Field(default=1, alias="AI_BACKEND_GEMINI_MAX_CONCURRENT_REQUESTS")
    gemini_min_request_interval_ms: int = Field(default=750, alias="AI_BACKEND_GEMINI_MIN_REQUEST_INTERVAL_MS")
    gemini_retry_attempts: int = Field(default=4, alias="AI_BACKEND_GEMINI_RETRY_ATTEMPTS")
    gemini_retry_base_delay_ms: int = Field(default=2000, alias="AI_BACKEND_GEMINI_RETRY_BASE_DELAY_MS")
    gemini_retry_max_delay_ms: int = Field(default=15000, alias="AI_BACKEND_GEMINI_RETRY_MAX_DELAY_MS")
    gemini_cooldown_on_429_ms: int = Field(default=20000, alias="AI_BACKEND_GEMINI_COOLDOWN_ON_429_MS")
    text_provider: str = Field(default="ollama", alias="AI_BACKEND_TEXT_PROVIDER")
    text_model: str = Field(default="gemma3", alias="AI_BACKEND_TEXT_MODEL")
    text_base_url: str = Field(default="http://localhost:11434", alias="AI_BACKEND_TEXT_BASE_URL")
    vision_provider: str = Field(default="ollama_vision", alias="AI_BACKEND_VISION_PROVIDER")
    vision_model: str = Field(default="qwen2.5vl:7b", alias="AI_BACKEND_VISION_MODEL")
    vision_base_url: str = Field(default="http://localhost:11434", alias="AI_BACKEND_VISION_BASE_URL")
    vision_timeout_seconds: int = Field(default=120, alias="AI_BACKEND_VISION_TIMEOUT_SECONDS")
    vision_timeout_retries: int = Field(default=2, alias="AI_BACKEND_VISION_TIMEOUT_RETRIES")
    vision_retry_delay_seconds: int = Field(default=5, alias="AI_BACKEND_VISION_RETRY_DELAY_SECONDS")
    vision_max_width: int = Field(default=512, alias="AI_BACKEND_VISION_MAX_WIDTH")
    vision_max_height: int = Field(default=1024, alias="AI_BACKEND_VISION_MAX_HEIGHT")
    ocr_enabled: bool = Field(default=True, alias="AI_BACKEND_OCR_ENABLED")
    ocr_min_confidence: float = Field(default=0.55, alias="AI_BACKEND_OCR_MIN_CONFIDENCE")
    ocr_max_text_lines: int = Field(default=20, alias="AI_BACKEND_OCR_MAX_TEXT_LINES")
    ocr_prefer_sfx: bool = Field(default=True, alias="AI_BACKEND_OCR_PREFER_SFX")
    ocr_debug_save_json: bool = Field(default=False, alias="AI_BACKEND_OCR_DEBUG_SAVE_JSON")
    llama_cpp_base_url: str = Field(default="http://127.0.0.1:8080/v1", alias="AI_BACKEND_LLAMA_CPP_BASE_URL")
    caption_chunk_size: int = Field(default=1, alias="AI_BACKEND_CAPTION_CHUNK_SIZE")
    caption_max_tokens: int = Field(default=512, alias="AI_BACKEND_CAPTION_MAX_TOKENS")
    script_chunk_size: int = Field(default=10, alias="AI_BACKEND_SCRIPT_CHUNK_SIZE")
    script_generation_retries: int = Field(default=2, alias="AI_BACKEND_SCRIPT_GENERATION_RETRIES")
    script_retry_delay_seconds: int = Field(default=3, alias="AI_BACKEND_SCRIPT_RETRY_DELAY_SECONDS")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def temp_root(self) -> Path:
        return Path(self.temp_root_raw).resolve()

    @property
    def ocr_debug_root(self) -> Path:
        return self.temp_root.parent / "ocr-debug"

    @property
    def effective_gemini_api_key(self) -> str:
        return _normalize_secret(self.gemini_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
