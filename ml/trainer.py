"""
ml/trainer.py — Trains a Random Forest Regressor on all products' sales history.

Why Random Forest?
  - Handles non-linear seasonality (e.g. weekend spikes, holiday dips)
  - No feature scaling required — trees are invariant to scale
  - Built-in feature importance: easy to explain WHY a prediction is high/low
  - Robust to outliers (common in perishables around promotions or stockouts)
  - Works well with relatively small datasets (1–2 years of daily data)

Training strategy:
  - All 30 products are trained in ONE model (a "global" model).
  - The product_id is NOT a feature — instead, lag + rolling features already
    encode the product's individual demand pattern.
  - Last 28 days per product are held out for evaluation (time-series split).
"""

import os
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from ml.feature_engineering import build_features, get_feature_matrix, FEATURE_COLS, TARGET_COL
from ml.model_store import save_model, make_version
from ml.config import MIN_DEMAND_THRESHOLD, SHOCK_PRODUCTS

log = logging.getLogger(__name__)

HOLDOUT_DAYS = 28   # days withheld per product for evaluation


def train(df: pd.DataFrame, model_dir: str) -> dict:
    """
    df: raw sales DataFrame with columns [product_id, sale_date, units_sold, price]
    Returns the saved artifact dict (includes mae, rmse, version).
    """
    # --- Exclude low-demand products from training and evaluation ---
    avg_demand = df.groupby("product_id")["units_sold"].mean()
    high_demand = avg_demand[avg_demand >= MIN_DEMAND_THRESHOLD].index.tolist()
    excluded   = avg_demand[avg_demand <  MIN_DEMAND_THRESHOLD].index.tolist()

    if excluded:
        log.info(
            "Excluding %d low-demand products (avg < %s units/day): %s",
            len(excluded), MIN_DEMAND_THRESHOLD, excluded,
        )
    df = df[df["product_id"].isin(high_demand)].copy()

    log.info("Building feature matrix from %d raw rows (%d products)...", len(df), len(high_demand))
    feat_df = build_features(df)

    # --- Time-series split: last HOLDOUT_DAYS rows per product go to test set ---
    feat_df = feat_df.sort_values(["product_id", "sale_date"])
    test_mask = feat_df.groupby("product_id").cumcount(ascending=False) < HOLDOUT_DAYS

    train_df = feat_df[~test_mask]
    test_df  = feat_df[test_mask]

    X_train, y_train = get_feature_matrix(train_df)
    X_test,  y_test  = get_feature_matrix(test_df)

    log.info("Train rows: %d | Test rows: %d", len(X_train), len(X_test))

    # --- Fit model ---
    rf = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,         # use all CPU cores
    )
    log.info("Fitting RandomForestRegressor (n_estimators=100)...")
    rf.fit(X_train, y_train)

    # --- Evaluate (global) — exclude shock products so synthetic anomalies don't skew metrics ---
    eval_mask  = ~test_df["product_id"].isin(SHOCK_PRODUCTS)
    X_eval     = test_df[eval_mask][FEATURE_COLS].values
    y_eval     = test_df[eval_mask][TARGET_COL].values
    preds_eval = np.clip(rf.predict(X_eval), 0, None)

    mae  = float(mean_absolute_error(y_eval, preds_eval))
    rmse = float(np.sqrt(mean_squared_error(y_eval, preds_eval)))
    log.info("Global evaluation — MAE: %.3f | RMSE: %.3f", mae, rmse)

    # --- Per-product MAE on holdout set (shock products skipped) ---
    per_product_mae = {}
    for pid in sorted(test_df["product_id"].unique()):
        if pid in SHOCK_PRODUCTS:
            continue
        mask     = test_df["product_id"] == pid
        X_p      = test_df[mask][FEATURE_COLS].values
        y_p      = test_df[mask][TARGET_COL].values
        pred_p   = np.clip(rf.predict(X_p), 0, None)
        per_product_mae[pid] = float(mean_absolute_error(y_p, pred_p))

    log.info("Per-product MAE (holdout, sorted best → worst):")
    for pid, p_mae in sorted(per_product_mae.items(), key=lambda x: x[1]):
        log.info("  %-25s %.2f", pid, p_mae)

    # --- Package and save ---
    artifact = {
        "model":        rf,
        "feature_cols": FEATURE_COLS,
        "version":      make_version(),
        "trained_at":   datetime.utcnow().isoformat(),
        "mae":          mae,
        "rmse":         rmse,
        "n_products":      len(high_demand),
        "n_excluded":      len(excluded),
        "per_product_mae": per_product_mae,
    }
    save_model(artifact, model_dir)
    return artifact
