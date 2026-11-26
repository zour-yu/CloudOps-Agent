"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for CloudOps-Agent."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-4-hydrogen"
    gemini_fallback_models: str = "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-4-argon"
    gemini_request_timeout: float = Field(default=30.0, gt=0.0)
    gemini_retry_attempts: int = Field(default=1, ge=1)
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
