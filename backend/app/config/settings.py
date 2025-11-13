"""Application configuration models and utilities."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    travio_id: int = Field(..., alias="TRAVIO_ID")
    travio_key: str = Field(..., alias="TRAVIO_KEY")
    travio_base_url: HttpUrl = Field(
        default="https://api.travio.it", alias="TRAVIO_BASE_URL"
    )
    travio_language: Literal["it", "en", "de", "ru", "es", "fr"] = Field(
        default="en", alias="TRAVIO_LANGUAGE"
    )
    use_mock_data: bool = Field(default=False, alias="USE_MOCK_DATA")
    app_name: str = Field(default="Travio Assistant Backend", alias="APP_NAME")

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"), env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached app settings instance."""
    return Settings()

