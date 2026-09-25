"""Test fixtures: an isolated SQLite database seeded with a small synthetic dataset."""

import os
import tempfile

import pytest

os.environ["AUTO_SEED"] = "false"
os.environ["MODEL_PATH"] = tempfile.mkdtemp(prefix="pv-models-")
os.environ["VECTOR_BACKEND"] = "json"
os.environ["SEED_REPORTS"] = "70"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app import db as dbmod  # noqa: E402


@pytest.fixture(scope="session")
def seeded():
    dbmod.configure_engine("sqlite://")
    from app.seed.seed import seed_all

    seed_all(verbose=False)
    yield


@pytest.fixture()
def db(seeded):
    s = dbmod.session_factory()()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="session")
def client(seeded):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def login(client, username="admin", password="Admin@2026"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    client.cookies.clear()  # tests authenticate with the bearer token explicitly
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return login(client)


@pytest.fixture(scope="session")
def officer(client):
    return login(client, "officer", "Officer@2026")
