from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None
_vector_column_configured = False


def configure_engine(url: str | None = None) -> Engine:
    """(Re)create the global engine. Tests call this with a SQLite URL."""
    global _engine, _SessionLocal, _vector_column_configured
    url = url or get_settings().database_url
    _vector_column_configured = False
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("postgresql"):
        # Fail health checks promptly when an external database is unreachable.
        kwargs["connect_args"] = {"connect_timeout": 3}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    _engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        configure_engine()
    assert _engine is not None
    return _engine


def session_factory() -> sessionmaker:
    if _SessionLocal is None:
        configure_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Iterator[Session]:
    configure_vector_column()
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


def is_postgres() -> bool:
    return get_engine().dialect.name == "postgresql"


def pgvector_available() -> bool:
    """True when running on Postgres with the `vector` extension installable."""
    settings = get_settings()
    if settings.vector_backend == "json" or not is_postgres():
        return False
    try:
        with get_engine().begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        return True
    except Exception:
        return False


def configure_vector_column() -> None:
    """Bind `embeddings.vector` to pgvector when available, once per process. Serverless
    deployments never run `init_db`, so requests call this; it creates no tables."""
    global _vector_column_configured
    if _vector_column_configured:
        return
    from app import models

    models.configure_vector_column(pgvector_available())
    _vector_column_configured = True


def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    configure_vector_column()
    Base.metadata.create_all(get_engine())


def check_db() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
