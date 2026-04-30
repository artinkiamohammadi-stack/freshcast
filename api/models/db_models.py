"""
api/models/db_models.py — SQLAlchemy ORM models.

Each class here maps to one table in MySQL.
SQLAlchemy translates Python attribute access (product.name)
into the correct SQL (SELECT name FROM products WHERE ...).
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text
from api.database import Base


class Product(Base):
    __tablename__ = "products"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    product_id      = Column(String(50), unique=True, nullable=False)
    name            = Column(String(100), nullable=False)
    category        = Column(String(50))
    shelf_life_days = Column(Integer, default=7)
    unit            = Column(String(20), default="units")


class SalesHistory(Base):
    __tablename__ = "sales_history"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    product_id  = Column(String(50), nullable=False)
    sale_date   = Column(Date, nullable=False)
    units_sold  = Column(Float, nullable=False)
    price       = Column(Float)


class Forecast(Base):
    __tablename__ = "forecasts"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    product_id       = Column(String(50), nullable=False)
    forecast_date    = Column(Date, nullable=False)
    predicted_units  = Column(Float, nullable=False)
    confidence_low   = Column(Float)
    confidence_high  = Column(Float)
    created_at       = Column(DateTime, default=datetime.utcnow)


class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    model_version = Column(String(50), nullable=False)
    trained_at    = Column(DateTime, nullable=False)
    mae           = Column(Float)
    rmse          = Column(Float)
    n_products    = Column(Integer)
    feature_names = Column(Text)   # JSON string
