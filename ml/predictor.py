"""
ml/predictor.py — Generate a multi-day demand forecast for one product.

Strategy: "iterative 1-day-ahead" forecasting.
  Day 1: use real historical lags → predict units_sold for day 1
  Day 2: use real history + day-1 prediction as lag → predict day 2
  ...and so on.

This lets us forecast further than 1 day without needing future ground truth.

Confidence interval: ±1.5 × rolling_std_7 of the last 7 residuals.
(Not a statistical guarantee — more of a "plausible range" for the dashboard.)
"""

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ml.feature_engineering import FEATURE_COLS

log = logging.getLogger(__name__)

CI_MULTIPLIER = 1.5   # width of confidence band as multiple of std dev


def predict(
    artifact: dict,
    history_df: pd.DataFrame,
    product_id: str,
    n_days: int = 7,
) -> list[dict]:
    """
    Parameters
    ----------
    artifact    : loaded model artifact from model_store.load_model()
    history_df  : DataFrame [product_id, sale_date, units_sold, price]
                  for ALL products (we need lags from full history)
    product_id  : which product to forecast
    n_days      : how many days ahead to forecast

    Returns
    -------
    List of dicts, one per forecast day:
      {forecast_date, predicted_units, confidence_low, confidence_high}
    """
    model       = artifact["model"]
    feature_cols = artifact["feature_cols"]

    # Work with this product's history only
    prod_df = history_df[history_df["product_id"] == product_id].copy()
    prod_df["sale_date"] = pd.to_datetime(prod_df["sale_date"])
    prod_df = prod_df.sort_values("sale_date").reset_index(drop=True)

    if len(prod_df) < 28:
        log.warning("Product %s has fewer than 28 history rows — forecast may be unreliable", product_id)

    # Fill any missing prices
    avg_price = prod_df["price"].mean() if prod_df["price"].notna().any() else 1.0
    prod_df["price"] = prod_df["price"].fillna(avg_price)

    last_date    = prod_df["sale_date"].max()
    avg_price_all = prod_df["price"].mean()

    # Append future rows one day at a time
    extended = prod_df.copy()
    forecasts = []

    for i in range(1, n_days + 1):
        forecast_date = last_date + timedelta(days=i)

        # Build the feature row for this future date
        row = _build_future_row(extended, forecast_date, avg_price_all, avg_price_all)
        feature_vector = np.array([[row[col] for col in feature_cols]])
        pred = float(np.clip(model.predict(feature_vector)[0], 0, None))

        # Confidence interval using rolling std of recent actuals
        recent_std = extended["units_sold"].tail(7).std()
        if np.isnan(recent_std) or recent_std == 0:
            recent_std = pred * 0.15   # fall back to 15% of prediction
        ci = CI_MULTIPLIER * recent_std

        forecasts.append({
            "forecast_date":    forecast_date.date() if hasattr(forecast_date, "date") else forecast_date,
            "predicted_units":  round(pred, 2),
            "confidence_low":   round(max(0.0, pred - ci), 2),
            "confidence_high":  round(pred + ci, 2),
        })

        # Add the prediction into the extended history so next day's lags are correct
        new_row = pd.DataFrame([{
            "product_id": product_id,
            "sale_date":  forecast_date,
            "units_sold": pred,
            "price":      avg_price_all,
        }])
        extended = pd.concat([extended, new_row], ignore_index=True)

    return forecasts


def _build_future_row(history: pd.DataFrame, target_date, price: float, avg_price: float) -> dict:
    """Compute feature values for a single future date using available history."""
    dt = pd.Timestamp(target_date)
    sales = history["units_sold"]

    def lag(n):
        idx = len(sales) - n
        return float(sales.iloc[idx]) if idx >= 0 else float(sales.mean())

    def rolling_mean(n):
        return float(sales.tail(n).mean()) if len(sales) >= 1 else 0.0

    def rolling_std(n):
        s = sales.tail(n).std()
        return float(s) if not np.isnan(s) else 1.0

    return {
        "day_of_week":    dt.dayofweek,
        "day_of_month":   dt.day,
        "week_of_year":   dt.isocalendar()[1],
        "month":          dt.month,
        "is_weekend":     int(dt.dayofweek >= 5),
        "lag_7":          lag(7),
        "lag_14":         lag(14),
        "lag_28":         lag(28),
        "rolling_mean_7":  rolling_mean(7),
        "rolling_mean_28": rolling_mean(28),
        "rolling_std_7":   rolling_std(7),
        "price":          price,
        "price_vs_avg":   (price / avg_price) if avg_price > 0 else 1.0,
    }
