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


def test_model_artifacts_load_without_the_original_files(db):
    from app.models import ModelArtifact
    from app.services.analysis_service import active_classifier, active_embedder, active_model

    clf = active_model(db, "sif_classifier")
    emb = active_model(db, "embedder")
    assert clf and emb
    assert db.get(ModelArtifact, clf.version)
    assert db.get(ModelArtifact, emb.version)
    clf.artifact_path = "missing/classifier.joblib"
    emb.artifact_path = "missing/embedder.joblib"
    assert active_classifier(db).version == clf.version
    assert active_embedder(db).version == emb.version


def test_login_works_without_analysis_tables_or_model_artifacts(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import Base, get_db
    from app.main import app
    from app.models import AuditLog, Role, User
    from app.security import ROLE_PERMISSIONS, hash_password

    monkeypatch.setenv("VERCEL", "1")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Role.__table__, User.__table__, AuditLog.__table__])
    assert not inspect(engine).has_table("model_artifacts")
    assert not inspect(engine).has_table("model_versions")
    make_session = sessionmaker(bind=engine)
    with make_session() as db:
        role = Role(name="HSE_ADMIN", label="HSE Admin", permissions=ROLE_PERMISSIONS["HSE_ADMIN"])
        db.add(role)
        db.flush()
        db.add(User(username="admin", full_name="HSE Admin (demo)", password_hash=hash_password("Admin@2026"), role_id=role.id))
        db.commit()

    def isolated_db():
        with make_session() as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app) as client:
            assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
            response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@2026"})
            assert response.status_code == 200
            assert response.json()["user"]["username"] == "admin"
            assert "pv_session" in response.cookies
            me = client.get("/api/auth/me")
            assert me.status_code == 200
            assert me.json()["user"]["username"] == "admin"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_requests_bind_pgvector_without_init_db(seeded, monkeypatch):
    """Vercel never runs init_db. Unless requests configure embeddings.vector, psycopg's
    text form of a pgvector value ("[0.12,...]") fails to load and /similar returns 500."""
    from sqlalchemy.dialects import postgresql

    from app import db as dbmod
    from app import models
    from app.models import Embedding

    vector_type = Embedding.__table__.c.vector.type
    monkeypatch.setattr(models, "_USE_PGVECTOR", False)
    monkeypatch.setattr(dbmod, "_vector_column_configured", False)
    with pytest.raises(ValueError):
        vector_type._cached_result_processor(postgresql.psycopg.dialect(), None)("[0.12,-0.5,0.3]")

    checks = []
    monkeypatch.setattr(dbmod, "pgvector_available", lambda: checks.append(1) or True)
    for _ in range(3):
        sessions = dbmod.get_db()
        next(sessions)
        sessions.close()
    assert checks == [1]
    load = vector_type._cached_result_processor(postgresql.psycopg.dialect(), None)
    assert load("[0.12,-0.5,0.3]") == pytest.approx([0.12, -0.5, 0.3])
