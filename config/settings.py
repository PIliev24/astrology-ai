"""
Centralized application settings using Pydantic Settings.

All environment variables are validated at startup. Missing required variables
will raise a ValidationError immediately, preventing the application from starting
with invalid configuration.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase Configuration
    supabase_url: str
    supabase_secret_key: str

    # RapidAPI Configuration
    rapidapi_key: str
    rapidapi_host: str = "astrologer.p.rapidapi.com"

    # Stripe Configuration
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_id_basic: str
    stripe_price_id_pro: str

    # Application Configuration
    frontend_url: str = "http://localhost:3000"
    log_level: str = "INFO"

    # Optional: Additional CORS origins (comma-separated)
    additional_cors_origins: Optional[str] = None

    @property
    def cors_origins(self) -> list[str]:
        """Get list of allowed CORS origins."""
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url)
        if self.additional_cors_origins:
            origins.extend(self.additional_cors_origins.split(","))
        return origins


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Settings are validated on first call. Subsequent calls return the cached instance.
    This ensures environment variables are validated exactly once at startup.

    Returns:
        Settings: Validated application settings

    Raises:
        pydantic.ValidationError: If required environment variables are missing
    """
    return Settings()
