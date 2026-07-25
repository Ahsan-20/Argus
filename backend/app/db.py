"""Database engine and session setup (Supabase Postgres via psycopg 3).

Falls back to a local SQLite file when DATABASE_URL is empty so the app can
boot on a fresh clone before Supabase is wired up.
"""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
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
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS track TEXT",
    "ALTER TABLE runs ADD COLUMN IF NOT EXISTS extracted TEXT",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS base_cadence_minutes INTEGER",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS stable_passes INTEGER DEFAULT 0",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS owner_email VARCHAR(255)",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS use_renderer BOOLEAN DEFAULT FALSE",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS is_shared BOOLEAN DEFAULT FALSE",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS previous_value TEXT",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS repeating BOOLEAN DEFAULT FALSE",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS consecutive_errors INTEGER DEFAULT 0",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS http_etag VARCHAR(255)",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS http_last_modified VARCHAR(64)",
    "ALTER TABLE watchers ADD COLUMN IF NOT EXISTS last_full_check_at TIMESTAMPTZ",
]

# The users table is created by create_all, but a deployment that already had
# an earlier version of it gets the newer columns here, same as above.
_ADDED_COLUMNS += [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_sent_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_used_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_requested_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_logins INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
]


def _ensure_columns() -> None:
    if engine.dialect.name != "postgresql":
        return  # the SQLite dev fallback is always created fresh
    with engine.begin() as conn:
        # Fail fast instead of hanging startup if some other session holds a
        # lock: the column almost certainly already exists, so a skipped ALTER
        # is harmless and the app still boots.
        conn.execute(text("SET lock_timeout = '4000'"))
        for stmt in _ADDED_COLUMNS:
            try:
                conn.execute(text(stmt))
            except OperationalError as exc:
                logging.getLogger("argus.db").warning(
                    "skipped migration (lock or timeout): %s", exc
                )
                conn.rollback()
                break
