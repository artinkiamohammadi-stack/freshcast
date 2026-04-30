"""
api/database.py — SQLAlchemy engine and session setup.

Supports two modes:
  - Local dev : set DATABASE_URL=sqlite:///./freshcast.db  (no server needed)
  - Docker    : set DB_HOST/DB_USER/etc. to connect to MySQL container
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # SQLite local dev path
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    )
else:
    # MySQL Docker path
    DATABASE_URL = (
        f"mysql+pymysql://"
        f"{os.getenv('DB_USER', 'freshcast')}:"
        f"{os.getenv('DB_PASSWORD', 'freshcast_pass')}@"
        f"{os.getenv('DB_HOST', 'db')}:"
        f"{os.getenv('DB_PORT', '3306')}/"
        f"{os.getenv('DB_NAME', 'freshcast')}"
        "?charset=utf8mb4"
    )
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
