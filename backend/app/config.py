from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://poorvabhas:poorvabhas_dev@localhost:5433/poorvabhas"
    secret_key: str = "dev-only-insecure-secret-change-me-in-env-file"
    environment: str = "demo"
    demo_mode: bool = True
    model_path: str = str(Path(__file__).resolve().parent.parent / "models_store")
    vector_backend: str = "auto"  # auto | pgvector | json
    cors_origins: str = "http://localhost:3000"
    access_token_minutes: int = 60 * 12
    cookie_secure: bool = False
    auto_seed: bool = True
    seed_reports: int = 280
    seed_random_state: int = 26165

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
