"""Deployment configuration: database URL normalisation, production secret guard,
cookie security defaults and the health-check status code."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import DEV_SECRET_KEY, InsecureConfigurationError, Settings, normalize_database_url, validate_production_settings

STRONG = "k" * 48
BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "url,expected",
    [
        ("postgresql://u:p@db.internal:5432/app", "postgresql+psycopg://u:p@db.internal:5432/app"),
        ("postgres://u:p@db.internal:5432/app", "postgresql+psycopg://u:p@db.internal:5432/app"),
        ("postgresql+psycopg://u:p@localhost:5433/poorvabhas", "postgresql+psycopg://u:p@localhost:5433/poorvabhas"),
        ("  postgresql://u:p@h/d?sslmode=require  ", "postgresql+psycopg://u:p@h/d?sslmode=require"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_database_url_normalisation(url, expected):
    assert normalize_database_url(url) == expected
    assert Settings(database_url=url).database_url == expected


def test_normalised_url_loads_the_installed_driver():
    from sqlalchemy import create_engine

    engine = create_engine(Settings(database_url="postgresql://u:p@localhost:1/d").database_url)
    assert engine.dialect.driver == "psycopg"


def test_cookie_secure_defaults_by_environment():
    assert Settings(environment="production", secret_key=STRONG).cookie_secure is True
    assert Settings(environment="Production ", secret_key=STRONG).cookie_secure is True
    assert Settings(environment="demo").cookie_secure is False
    assert Settings(environment="development").cookie_secure is False
    # an explicit value always wins
    assert Settings(environment="production", secret_key=STRONG, cookie_secure=False).cookie_secure is False
    assert Settings(environment="demo", cookie_secure=True).cookie_secure is True


@pytest.mark.parametrize("secret", [DEV_SECRET_KEY, "compose-demo-secret-change-me-before-any-real-use-0123456789", "replace-with-a-long-random-secret", "", "   "])
def test_production_refuses_published_or_empty_secret(secret):
    with pytest.raises(InsecureConfigurationError) as exc:
        validate_production_settings(Settings(environment="production", secret_key=secret))
    if secret.strip():
        assert secret not in str(exc.value)


def test_non_production_and_strong_secret_are_allowed():
    validate_production_settings(Settings(environment="demo", secret_key=DEV_SECRET_KEY))
    validate_production_settings(Settings(environment="production", secret_key=STRONG))


def _import_app(extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "ENVIRONMENT")}
    env.update(extra_env)
    return subprocess.run([sys.executable, "-c", "import app.main"], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120)


def test_app_refuses_to_start_in_production_with_default_secret():
    r = _import_app({"ENVIRONMENT": "production", "AUTO_SEED": "false"})
    assert r.returncode != 0
    assert "Refusing to start" in r.stderr
    assert DEV_SECRET_KEY not in r.stderr + r.stdout


def test_app_starts_in_production_with_strong_secret():
    r = _import_app({"ENVIRONMENT": "production", "SECRET_KEY": STRONG, "AUTO_SEED": "false"})
    assert r.returncode == 0, r.stderr
    assert STRONG not in r.stderr + r.stdout


def test_health_returns_503_when_database_unavailable(client, monkeypatch):
    import app.main as main

    assert client.get("/api/health").status_code == 200
    monkeypatch.setattr(main, "check_db", lambda: False)
    r = client.get("/api/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded" and body["database"] == "unavailable"
    text = r.text.lower()
    assert "postgres" not in text and "password" not in text and "secret" not in text
