"""Configuration management for Findable."""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings read from environment variables or .env file."""

    # PayPal Sandbox Configuration
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    PAYPAL_WEBHOOK_ID: str = ""

    # LLM Provider Configuration
    LLM_PROVIDER: Literal["anthropic", "gemini", "groq"] = "groq"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "claude-3-5-sonnet-20241022"

    # Application Settings
    APP_BASE_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite:///findable.db"
    PASSPORT_SECRET: str = "dev-secret-key-32-bytes-findable-2026-auth"

    # Mock Mode (1 enables mock PayPal operations without credentials)
    MOCK_PAYPAL: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
