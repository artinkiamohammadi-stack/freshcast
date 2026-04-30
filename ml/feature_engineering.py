"""
ml/feature_engineering.py — Turns raw sales rows into ML-ready features.

Why these features?
  - Calendar features capture weekly/seasonal buying patterns
    (people buy more bread on Friday, more milk in January).
  - Lag features let the model "see" recent demand history
    (last week's sales are the strongest predictor of this week's).
  - Rolling statistics smooth out noise and expose trends.
  - Price features let the model learn price-sensitivity.

Input:  DataFrame with columns [product_id, sale_date, units_sold, price]
Output: DataFrame with the original columns PLUS all feature columns below.
        Rows with NaN lags (first 28 days per product) are dropped.
"""

import pandas as pd
import numpy as np


FEATURE_COLS = [
    # --- Calendar ---
    "day_of_week",     # 0=Mon … 6=Sun
    "day_of_month",
    "week_of_year",
    "month",
    "is_weekend",      # Sat or Sun → higher retail traffic
    # --- Lag sales (same day 1/2/4 weeks ago) ---
    "lag_7",
    "lag_14",
    "lag_28",
    # --- Rolling statistics ---
    "rolling_mean_7",   # avg sales over last 7 days
    "rolling_mean_28",  # avg sales over last 28 days
    "rolling_std_7",    # volatility over last 7 days (used for confidence intervals too)
    # --- Price ---
    "price",
    "price_vs_avg",    # sell_price / product's all-time avg price
]

TARGET_COL = "units_sold"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all feature columns to df and drop rows that have NaN lags.
    df must be sorted by (product_id, sale_date) before calling.
    """
    df = df.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    df = df.sort_values(["product_id", "sale_date"]).reset_index(drop=True)

    # --- Calendar features ---
    df["day_of_week"]  = df["sale_date"].dt.dayofweek
    df["day_of_month"] = df["sale_date"].dt.day
    df["week_of_year"] = df["sale_date"].dt.isocalendar().week.astype(int)
    df["month"]        = df["sale_date"].dt.month
    df["is_weekend"]   = (df["day_of_week"] >= 5).astype(int)

    # --- Lag and rolling features (computed per product to avoid data leakage) ---
    grp = df.groupby("product_id")["units_sold"]

    df["lag_7"]  = grp.shift(7)
    df["lag_14"] = grp.shift(14)
    df["lag_28"] = grp.shift(28)

    df["rolling_mean_7"]  = grp.transform(lambda s: s.shift(1).rolling(7,  min_periods=1).mean())
    df["rolling_mean_28"] = grp.transform(lambda s: s.shift(1).rolling(28, min_periods=1).mean())
    df["rolling_std_7"]   = grp.transform(lambda s: s.shift(1).rolling(7,  min_periods=2).std().fillna(1.0))

    # --- Price features ---
    avg_price = df.groupby("product_id")["price"].transform("mean")
    df["price_vs_avg"] = df["price"] / avg_price.replace(0, np.nan)
    df["price_vs_avg"] = df["price_vs_avg"].fillna(1.0)

    # Fill any remaining NaN prices with 1.0 (neutral)
    df["price"] = df["price"].fillna(1.0)

    # Drop the first 28 days per product — lags are undefined there
    df = df.dropna(subset=["lag_7", "lag_14", "lag_28"]).reset_index(drop=True)

    return df


def get_feature_matrix(df: pd.DataFrame):
    """
    Return (X, y) — numpy arrays ready for scikit-learn.
    Call build_features() first.
    """
    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values
    return X, y
