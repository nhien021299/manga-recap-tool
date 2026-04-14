from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", alias="AI_BACKEND_HOST")
    port: int = Field(default=8000, alias="AI_BACKEND_PORT")
    api_prefix: str = "/api/v1"
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="AI_BACKEND_CORS_ORIGINS")
    temp_root_raw: str = Field(default=".temp/jobs", alias="AI_BACKEND_TEMP_ROOT")
    text_provider: str = Field(default="ollama", alias="AI_BACKEND_TEXT_PROVIDER")
    text_model: str = Field(default="llama3", alias="AI_BACKEND_TEXT_MODEL")
    text_base_url: str = Field(default="http://localhost:11434", alias="AI_BACKEND_TEXT_BASE_URL")
    vision_provider: str = Field(default="ollama_vision", alias="AI_BACKEND_VISION_PROVIDER")
    vision_model: str = Field(default="gemma3", alias="AI_BACKEND_VISION_MODEL")
    vision_base_url: str = Field(default="http://localhost:11434", alias="AI_BACKEND_VISION_BASE_URL")
    llama_cpp_base_url: str = Field(default="http://127.0.0.1:8080/v1", alias="AI_BACKEND_LLAMA_CPP_BASE_URL")
    caption_chunk_size: int = Field(default=4, alias="AI_BACKEND_CAPTION_CHUNK_SIZE")
    script_chunk_size: int = Field(default=10, alias="AI_BACKEND_SCRIPT_CHUNK_SIZE")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def temp_root(self) -> Path:
        return Path(self.temp_root_raw).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
