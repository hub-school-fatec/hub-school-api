from functools import lru_cache
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_jwt_issuer: str = ""
    supabase_anon_key: str = ""
    supabase_publishable_key: str = ""
    cors_allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("cors_allowed_origins")
    @classmethod
    def explicit_origins(cls, origins: list[str]) -> list[str]:
        if any(not origin or origin == "*" or origin.endswith("/") for origin in origins):
            raise ValueError("CORS exige origens explícitas sem barra final")
        return origins

    def auth_project_url(self) -> str | None:
        url = self.supabase_url.rstrip("/")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path):
            return None
        if self.supabase_jwt_issuer != f"{url}/auth/v1":
            return None
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
