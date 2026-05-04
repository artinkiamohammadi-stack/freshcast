"""
api/database.py — SQLAlchemy engine and session setup.

Engine selection order:
  1. Use DATABASE_URL if set.
  2. If DATABASE_URL is absent, build a MySQL URL from DB_HOST/DB_USER/etc.
  3. If the URL is MySQL and the hostname is 'db' (docker-compose only) or the
     connection attempt fails, fall back to SQLite automatically.

This means the app works in three configurations with zero manual changes:
  - docker-compose  : MySQL container reachable at 'db'
  - Azure (managed) : Pass a real DATABASE_URL pointing at Azure MySQL/Postgres
  - Standalone / CI : No DATABASE_URL → SQLite
"""

import os
import logging
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_SQLITE_URL  = "sqlite:///./freshcast.db"
_SQLITE_ARGS = {"check_same_thread": False}


def _mysql_url_from_env() -> str:
    return (
        f"mysql+pymysql://"
        f"{os.getenv('DB_USER', 'freshcast')}:"
        f"{os.getenv('DB_PASSWORD', 'freshcast_pass')}@"
        f"{os.getenv('DB_HOST', 'db')}:"
        f"{os.getenv('DB_PORT', '3306')}/"
        f"{os.getenv('DB_NAME', 'freshcast')}"
        "?charset=utf8mb4"
    )


def _reachable(engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.warning("Database connection test failed: %s", exc)
        return False


def _sqlite_engine():
    log.info("Using SQLite: %s", _SQLITE_URL)
    return create_engine(_SQLITE_URL, connect_args=_SQLITE_ARGS)


def _make_engine():
    url = os.getenv("DATABASE_URL") or _mysql_url_from_env()

    # Non-MySQL (e.g. SQLite passed explicitly) — use as-is
    if not url.startswith("mysql"):
        log.info("Using database: %s", url)
        return create_engine(url, connect_args=_SQLITE_ARGS)

    # MySQL path: 'db' hostname only exists inside docker-compose
    hostname = urlparse(url).hostname
    if hostname == "db":
        log.info("MySQL hostname is 'db' — testing docker-compose connection...")
        candidate = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
        if _reachable(candidate):
            log.info("MySQL connection succeeded.")
            return candidate
        log.warning("MySQL at 'db' unreachable — falling back to SQLite.")
        return _sqlite_engine()

    # External MySQL (e.g. Azure Database for MySQL) — try it, fall back on failure
    log.info("Connecting to MySQL at %s...", hostname)
    candidate = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
    if _reachable(candidate):
        log.info("MySQL connection succeeded.")
        return candidate
    log.warning("MySQL connection failed — falling back to SQLite.")
    return _sqlite_engine()


engine       = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
