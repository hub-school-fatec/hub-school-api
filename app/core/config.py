from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_jwt_issuer: str | None = None
    cors_origins: list[str] = []
    minimum_attendance: Decimal = Field(default=Decimal('75'), gt=0, le=100)
    minimum_grade: Decimal = Field(default=Decimal('6'), ge=0)
    jwks_cache_seconds: int = Field(default=300, ge=1, le=3600)
    jwks_timeout_seconds: int = Field(default=5, ge=1, le=30)
    attachment_max_bytes: int = Field(default=10_000_000, gt=0, le=100_000_000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
