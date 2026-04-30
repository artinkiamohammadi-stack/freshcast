"""
api/routes/forecast.py

GET /forecast/{product_id}?days=7

Loads the trained model and historical sales from MySQL,
then runs the iterative predictor to generate a multi-day forecast.
Forecast results are also saved back to the forecasts table so they
can be reviewed later without re-running the model.
"""

import os
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.db_models import Product, SalesHistory, Forecast
from api.models.schemas import ForecastResponse, ForecastPoint
from ml.model_store import load_model
from ml.predictor import predict
from ml.config import MIN_DEMAND_THRESHOLD

log = logging.getLogger(__name__)
router = APIRouter()

MODEL_DIR = os.getenv("MODEL_DIR", str(Path(__file__).parent.parent.parent / "models"))


@router.get("/forecast/{product_id}", response_model=ForecastResponse, tags=["Forecast"])
def get_forecast(
    product_id: str,
    days: int = Query(default=7, ge=1, le=28, description="Number of future days to forecast"),
    db: Session = Depends(get_db),
):
    """
    Generate a demand forecast for the given product.

    The model needs at least 28 days of history to compute lag features.
    Returns predicted_units plus a confidence interval for each day.
    """
    # Verify product exists
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")

    # Load trained model
    artifact = load_model(MODEL_DIR)
    if artifact is None:
        raise HTTPException(
            status_code=503,
            detail="Model not trained yet. Call POST /retrain first.",
        )

    # Only fetch this product's history — the predictor only needs lag features
    # which look back 28 days max, so 60 rows is more than enough.
    product_sales = (
        db.query(SalesHistory)
        .filter(SalesHistory.product_id == product_id)
        .order_by(SalesHistory.sale_date.desc())
        .limit(60)
        .all()
    )
    if not product_sales:
        raise HTTPException(status_code=503, detail="No sales history in database. Has the seed run?")

    history_df = pd.DataFrame([
        {"product_id": r.product_id, "sale_date": r.sale_date,
         "units_sold": r.units_sold, "price": r.price}
        for r in product_sales
    ])

    # Reject low-demand products before running the model
    avg_demand = history_df["units_sold"].mean()
    if avg_demand < MIN_DEMAND_THRESHOLD:
        log.info(
            "Product %s has avg demand %.2f < threshold %s — returning insufficient.",
            product_id, avg_demand, MIN_DEMAND_THRESHOLD,
        )
        return ForecastResponse(
            product_id=product_id,
            forecasts=[],
            insufficient=True,
            reason="Insufficient demand volume for reliable forecasting",
        )

    # Run prediction
    try:
        raw_forecasts = predict(artifact, history_df, product_id, n_days=days)
    except Exception as e:
        log.exception("Prediction failed for %s", product_id)
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

    # Persist forecasts to DB (upsert by product+date: delete old, insert new)
    forecast_dates = [f["forecast_date"] for f in raw_forecasts]
    db.query(Forecast).filter(
        Forecast.product_id == product_id,
        Forecast.forecast_date.in_(forecast_dates),
    ).delete(synchronize_session=False)

    for f in raw_forecasts:
        db.add(Forecast(
            product_id=product_id,
            forecast_date=f["forecast_date"],
            predicted_units=f["predicted_units"],
            confidence_low=f["confidence_low"],
            confidence_high=f["confidence_high"],
            created_at=datetime.utcnow(),
        ))
    db.commit()

    points = [
        ForecastPoint(
            forecast_date=f["forecast_date"],
            predicted_units=f["predicted_units"],
            confidence_low=f["confidence_low"],
            confidence_high=f["confidence_high"],
        )
        for f in raw_forecasts
    ]
    return ForecastResponse(product_id=product_id, forecasts=points)
