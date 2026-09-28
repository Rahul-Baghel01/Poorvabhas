from functools import lru_cache
import os
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-only-insecure-secret-change-me-in-env-file"
# Secrets published in this repository (config default, docker-compose default, .env.example
# placeholder). None of them may be used when ENVIRONMENT=production.
KNOWN_INSECURE_SECRETS = frozenset(
    {
        DEV_SECRET_KEY,
        "compose-demo-secret-change-me-before-any-real-use-0123456789",
        "replace-with-a-long-random-secret",
    }
)


class InsecureConfigurationError(RuntimeError):
    pass


def normalize_database_url(url: str) -> str:
    """Providers such as Neon hand out postgres:// or postgresql:// URLs; SQLAlchemy would
    pick the psycopg2 driver for those, but this app ships psycopg 3."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://poorvabhas:poorvabhas_dev@localhost:5433/poorvabhas"
    secret_key: str = DEV_SECRET_KEY
    environment: str = "demo"
    demo_mode: bool = True
    model_path: str = str(Path("/tmp/poorvabhas-models") if os.environ.get("VERCEL") else Path(__file__).resolve().parent.parent / "models_store")
    vector_backend: str = "auto"  # auto | pgvector | json
    cors_origins: str = "http://localhost:3000"
    access_token_minutes: int = 60 * 12
    cookie_secure: bool | None = None  # unset -> true in production, false otherwise
    auto_seed: bool = True
    seed_reports: int = 280
    seed_random_state: int = 26165

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @model_validator(mode="after")
    def _environment_defaults(self) -> "Settings":
        if self.cookie_secure is None:
            self.cookie_secure = self.is_production
        return self

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def validate_production_settings(settings: Settings) -> None:
    """Refuse to run production with a published secret. Never includes the secret in the message."""
    if settings.is_production and (not settings.secret_key.strip() or settings.secret_key in KNOWN_INSECURE_SECRETS):
        raise InsecureConfigurationError(
            "Refusing to start: ENVIRONMENT=production but SECRET_KEY is empty or a published development "
            "default. Set SECRET_KEY to a long random value, e.g. "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
