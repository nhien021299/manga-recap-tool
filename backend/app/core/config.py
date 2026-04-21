from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
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
    tts_provider: str = Field(default="vieneu", alias="AI_BACKEND_TTS_PROVIDER")
    tts_runtime: str = Field(default="auto", alias="AI_BACKEND_TTS_RUNTIME")
    tts_warm_on_startup: bool = Field(default=False, alias="AI_BACKEND_TTS_WARM_ON_STARTUP")
    tts_smoke_test_text: str = Field(default="", alias="AI_BACKEND_TTS_SMOKE_TEST_TEXT")
    tts_max_concurrent_jobs: int = Field(default=1, alias="AI_BACKEND_TTS_MAX_CONCURRENT_JOBS")
    tts_vieneu_default_voice_key: str = Field(default="default", alias="AI_BACKEND_TTS_VIENEU_VOICE_KEY")
    tts_f5_python_raw: str = Field(
        default=".bench/f5-venv/Scripts/python.exe",
        alias="AI_BACKEND_TTS_F5_PYTHON",
    )
    tts_f5_model_root_raw: str = Field(default=".models/f5-onnx", alias="AI_BACKEND_TTS_F5_MODEL_ROOT")
    tts_f5_reference_root_raw: str = Field(
        default=".models/f5-reference",
        alias="AI_BACKEND_TTS_F5_REFERENCE_ROOT",
    )
    tts_f5_default_voice_key: str = Field(
        default="nu_review_cuon",
        alias="AI_BACKEND_TTS_F5_VOICE_KEY",
    )
    tts_f5_gpu_bundle: str = Field(default="GPU_CUDA_F16", alias="AI_BACKEND_TTS_F5_GPU_BUNDLE")
    tts_f5_cpu_bundle: str = Field(default="CPU_F32", alias="AI_BACKEND_TTS_F5_CPU_BUNDLE")
    caption_chunk_size: int = Field(default=1, alias="AI_BACKEND_CAPTION_CHUNK_SIZE")
    caption_max_tokens: int = Field(default=512, alias="AI_BACKEND_CAPTION_MAX_TOKENS")
    script_chunk_size: int = Field(default=10, alias="AI_BACKEND_SCRIPT_CHUNK_SIZE")
    script_generation_retries: int = Field(default=2, alias="AI_BACKEND_SCRIPT_GENERATION_RETRIES")
    script_retry_delay_seconds: int = Field(default=3, alias="AI_BACKEND_SCRIPT_RETRY_DELAY_SECONDS")

    @field_validator("tts_runtime", mode="before")
    @classmethod
    def _normalize_tts_runtime(cls, value: object) -> str:
        if value is None:
            return "auto"
        normalized = str(value).strip().lower()
        if normalized in {"", "auto", "cpu", "gpu"}:
            return normalized or "auto"
        raise ValueError("AI_BACKEND_TTS_RUNTIME must be one of: auto, cpu, gpu.")

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
            return "vieneu"
        normalized = str(value).strip().lower()
        if normalized in {"", "vieneu", "f5"}:
            return normalized or "vieneu"
        raise ValueError("AI_BACKEND_TTS_PROVIDER must be one of: vieneu, f5.")

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
    def tts_f5_python(self) -> Path:
        return Path(self.tts_f5_python_raw).resolve()

    @property
    def tts_f5_model_root(self) -> Path:
        return Path(self.tts_f5_model_root_raw).resolve()

    @property
    def tts_f5_reference_root(self) -> Path:
        return Path(self.tts_f5_reference_root_raw).resolve()

    @property
    def effective_gemini_api_key(self) -> str:
        return _normalize_secret(self.gemini_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
