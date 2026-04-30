"""
api/models/schemas.py — Pydantic models for API request/response validation.

Pydantic automatically:
  - Validates incoming data types
  - Converts Python objects → JSON (serialization)
  - Generates the /docs API reference automatically

These are separate from the SQLAlchemy ORM models — one layer reads from DB,
the other layer defines what JSON shape the API sends back to the client.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class ProductOut(BaseModel):
    product_id:      str
    name:            str
    category:        Optional[str]
    shelf_life_days: Optional[int]
    unit:            Optional[str]

    model_config = {"from_attributes": True}


class SalePoint(BaseModel):
    sale_date:  date
    units_sold: float
    price:      Optional[float]

    model_config = {"from_attributes": True}


class ForecastPoint(BaseModel):
    forecast_date:   date
    predicted_units: float
    confidence_low:  Optional[float]
    confidence_high: Optional[float]

    model_config = {"from_attributes": True}


class ForecastResponse(BaseModel):
    product_id:   str
    forecasts:    list[ForecastPoint]
    insufficient: bool = False
    reason:       Optional[str] = None


class HistoryResponse(BaseModel):
    product_id: str
    history:    list[SalePoint]


class RetrainResponse(BaseModel):
    status:        str
    model_version: str
    trained_at:    str
    mae:           float
    rmse:          float
    n_products:    int


class ModelInfoResponse(BaseModel):
    model_version: Optional[str]
    trained_at:    Optional[str]
    mae:           Optional[float]
    rmse:          Optional[float]
    n_products:    Optional[int]
    feature_names: Optional[list[str]]
