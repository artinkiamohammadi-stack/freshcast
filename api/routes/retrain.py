"""
api/routes/retrain.py

POST /retrain

Pulls all sales history from MySQL, runs the full ML training pipeline,
saves the new model artifact, and records the training metadata to DB.

In production this would be triggered on a schedule (e.g. nightly).
For the portfolio demo it's exposed as a manual API endpoint.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.db_models import SalesHistory, ModelMetadata
from api.models.schemas import RetrainResponse
from ml.trainer import train

log = logging.getLogger(__name__)
router = APIRouter()

MODEL_DIR = os.getenv("MODEL_DIR", str(Path(__file__).parent.parent.parent / "models"))

# Simple flag to prevent concurrent retraining
_is_training = False


@router.post("/retrain", response_model=RetrainResponse, tags=["Model"])
def retrain(db: Session = Depends(get_db)):
    """
    Trigger a full model retrain on the current sales history in MySQL.

    Returns model version, evaluation metrics (MAE / RMSE), and timestamp.
    MAE = Mean Absolute Error (avg units off per day — lower is better).
    RMSE = Root Mean Squared Error (penalises big errors more).
    """
    global _is_training
    if _is_training:
        raise HTTPException(status_code=409, detail="Training already in progress. Try again shortly.")

    # Load all history from DB into a DataFrame
    rows = db.query(SalesHistory).all()
    if not rows:
        raise HTTPException(status_code=503, detail="No sales data in DB. Run the seed first.")

    df = pd.DataFrame([
        {"product_id": r.product_id, "sale_date": r.sale_date,
         "units_sold": r.units_sold, "price": r.price}
        for r in rows
    ])

    log.info("Starting retrain on %d rows across %d products", len(df), df["product_id"].nunique())

    _is_training = True
    try:
        artifact = train(df, MODEL_DIR)
    except Exception as e:
        log.exception("Training failed")
        raise HTTPException(status_code=500, detail=f"Training error: {str(e)}")
    finally:
        _is_training = False

    # Save training metadata to DB
    meta = ModelMetadata(
        model_version=artifact["version"],
        trained_at=datetime.utcnow(),
        mae=artifact["mae"],
        rmse=artifact["rmse"],
        n_products=artifact["n_products"],
        feature_names=json.dumps(artifact["feature_cols"]),
    )
    db.add(meta)
    db.commit()

    log.info("Retrain complete — version=%s MAE=%.3f RMSE=%.3f", artifact["version"], artifact["mae"], artifact["rmse"])

    return RetrainResponse(
        status="ok",
        model_version=artifact["version"],
        trained_at=artifact["trained_at"],
        mae=artifact["mae"],
        rmse=artifact["rmse"],
        n_products=artifact["n_products"],
    )
