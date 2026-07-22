"""Database engine and session setup (Supabase Postgres via psycopg 3).

Falls back to a local SQLite file when DATABASE_URL is empty so the app can
boot on a fresh clone before Supabase is wired up.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()


def _normalize_url(url: str) -> str:
    """Force the psycopg 3 driver and dev SQLite fallback."""
    if not url:
        return "sqlite:///./argus_dev.db"
    # Supabase hands out `postgresql://...`; point SQLAlchemy at psycopg 3.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(
    _normalize_url(settings.database_url),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables on startup (no Alembic needed at this size)."""
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


# create_all only creates missing TABLES, never missing columns. This handles
# the handful of columns added after a table already existed. Idempotent, so it
# is safe to run on every startup. If the schema churns much more than this,
# switch to Alembic.
_ADDED_COLUMNS = [
    "ALTER TABLE runs ADD COLUMN IF NOT EXISTS provider VARCHAR(16)",
    "ALTER TABLE runs ADD COLUMN IF NOT EXISTS model VARCHAR(64)",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE",
]


def _ensure_columns() -> None:
    if engine.dialect.name != "postgresql":
        return  # the SQLite dev fallback is always created fresh
    with engine.begin() as conn:
        for stmt in _ADDED_COLUMNS:
            conn.execute(text(stmt))
