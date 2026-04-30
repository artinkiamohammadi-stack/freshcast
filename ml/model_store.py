"""
ml/model_store.py — Save and load trained model artifacts using joblib.

joblib is better than pickle for scikit-learn models because it handles
large numpy arrays more efficiently (memory-mapped files).

Stored artifact is a dict:
  {
    "model":         RandomForestRegressor instance,
    "feature_cols":  list of feature column names,
    "version":       "v1_YYYYMMDD_HHMMSS",
    "trained_at":    datetime string,
    "mae":           float,
    "rmse":          float,
    "n_products":    int,
  }
"""

import os
import logging
from datetime import datetime

import joblib

log = logging.getLogger(__name__)

MODEL_FILENAME = "freshcast_model.pkl"

# In-memory cache — model is loaded from disk once, then reused for every request
_cache: dict | None = None


def get_model_path(model_dir: str) -> str:
    return os.path.join(model_dir, MODEL_FILENAME)


def save_model(artifact: dict, model_dir: str):
    global _cache
    os.makedirs(model_dir, exist_ok=True)
    path = get_model_path(model_dir)
    joblib.dump(artifact, path, compress=3)
    _cache = artifact   # update cache immediately so retraining takes effect without reload
    log.info("Model saved to %s  (MAE=%.3f, RMSE=%.3f)", path, artifact["mae"], artifact["rmse"])


def load_model(model_dir: str) -> dict | None:
    """Return the artifact dict from cache, or load from disk on first call."""
    global _cache
    if _cache is not None:
        return _cache
    path = get_model_path(model_dir)
    if not os.path.exists(path):
        log.warning("No trained model found at %s. Run POST /retrain first.", path)
        return None
    _cache = joblib.load(path)
    log.info("Model loaded from disk %s  (version=%s)", path, _cache.get("version"))
    return _cache


def make_version() -> str:
    return "v1_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S")
