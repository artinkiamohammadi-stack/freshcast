"""
api/main.py — FastAPI application entry point.

Interactive API docs (great for demos):
  http://localhost:8000/docs   (Swagger UI)
  http://localhost:8000/redoc  (ReDoc)

Dashboard (local dev, served by FastAPI):
  http://localhost:8000

On startup:
  1. Creates DB tables (SQLite: auto-creates file; MySQL: tables must exist via init.sql)
  2. Seeds synthetic data if products table is empty
  3. Trains initial model if no .pkl file exists yet
"""

import os
import sys
import time
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import products, forecast, retrain

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger(__name__)

app = FastAPI(
    title="FreshCast API",
    description="Demand forecasting for perishable goods",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(forecast.router)
app.include_router(retrain.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# Serve the frontend as static files when running locally (without Nginx).
# API routes registered above take priority over the catch-all static mount.
_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


@app.on_event("startup")
def startup():
    _create_tables()
    _maybe_seed()
    _maybe_train()


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_tables():
    """Create all ORM tables. For SQLite this also creates the .db file."""
    from api.database import engine, Base
    import api.models.db_models  # ensure models are registered with Base
    Base.metadata.create_all(bind=engine)
    log.info("Database tables ready.")


def _wait_for_mysql(max_attempts: int = 30, delay: float = 3.0):
    """Only called when using MySQL (Docker mode)."""
    import pymysql
    for attempt in range(1, max_attempts + 1):
        try:
            conn = pymysql.connect(
                host=os.getenv("DB_HOST", "db"),
                port=int(os.getenv("DB_PORT", 3306)),
                user=os.getenv("DB_USER", "freshcast"),
                password=os.getenv("DB_PASSWORD", "freshcast_pass"),
                database=os.getenv("DB_NAME", "freshcast"),
            )
            conn.close()
            log.info("MySQL is ready.")
            return
        except pymysql.Error as e:
            log.info("Waiting for MySQL (%d/%d): %s", attempt, max_attempts, e)
            time.sleep(delay)
    log.error("MySQL did not become ready in time.")
    sys.exit(1)


def _maybe_seed():
    """Seed the DB with synthetic data if the products table is empty."""
    # For MySQL mode, wait for the server first
    if not os.getenv("DATABASE_URL"):
        _wait_for_mysql()

    try:
        from db.seed import run_seed
        run_seed()
    except Exception as e:
        log.error("Seed failed: %s", e)


def _maybe_train():
    """Train the model on startup if no saved model exists yet."""
    model_dir = os.getenv("MODEL_DIR", str(Path(__file__).parent.parent / "models"))
    model_path = os.path.join(model_dir, "freshcast_model.pkl")

    if os.path.exists(model_path):
        log.info("Existing model found — skipping initial training.")
        return

    log.info("No model found — running initial training...")
    try:
        import pandas as pd
        from api.database import SessionLocal
        from api.models.db_models import SalesHistory

        db = SessionLocal()
        rows = db.query(SalesHistory).all()
        db.close()

        if not rows:
            log.warning("No sales data — skipping initial training.")
            return

        df = pd.DataFrame([
            {"product_id": r.product_id, "sale_date": r.sale_date,
             "units_sold": r.units_sold, "price": r.price}
            for r in rows
        ])
        from ml.trainer import train
        train(df, model_dir)
        log.info("Initial training complete.")
    except Exception as e:
        log.error("Initial training failed: %s", e)
