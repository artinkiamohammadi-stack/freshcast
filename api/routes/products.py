"""
api/routes/products.py

GET /products              → list all tracked products
GET /products/{id}/history → historical daily sales for one product
GET /model-info            → latest model training metadata
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.db_models import Product, SalesHistory, ModelMetadata
from api.models.schemas import ProductOut, HistoryResponse, SalePoint, ModelInfoResponse

router = APIRouter()


@router.get("/products", response_model=list[ProductOut], tags=["Products"])
def list_products(db: Session = Depends(get_db)):
    """Return all products with their category and shelf-life metadata."""
    products = db.query(Product).order_by(Product.name).all()
    return products


@router.get("/products/{product_id}/history", response_model=HistoryResponse, tags=["Products"])
def get_history(
    product_id: str,
    days: int = Query(default=90, ge=7, le=1825, description="Number of past days to return"),
    db: Session = Depends(get_db),
):
    """
    Return the last N days of daily sales for a single product.
    Used by the dashboard to draw the historical section of the forecast chart.
    """
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")

    rows = (
        db.query(SalesHistory)
        .filter(SalesHistory.product_id == product_id)
        .order_by(SalesHistory.sale_date.desc())
        .limit(days)
        .all()
    )
    # Return in chronological order
    rows = sorted(rows, key=lambda r: r.sale_date)
    history = [SalePoint(sale_date=r.sale_date, units_sold=r.units_sold, price=r.price) for r in rows]
    return HistoryResponse(product_id=product_id, history=history)


@router.get("/model-info", response_model=ModelInfoResponse, tags=["Model"])
def get_model_info(db: Session = Depends(get_db)):
    """Return metadata about the most recently trained model."""
    meta = (
        db.query(ModelMetadata)
        .order_by(ModelMetadata.trained_at.desc())
        .first()
    )
    if not meta:
        return ModelInfoResponse(
            model_version=None, trained_at=None, mae=None,
            rmse=None, n_products=None, feature_names=None
        )
    features = json.loads(meta.feature_names) if meta.feature_names else None
    return ModelInfoResponse(
        model_version=meta.model_version,
        trained_at=str(meta.trained_at),
        mae=meta.mae,
        rmse=meta.rmse,
        n_products=meta.n_products,
        feature_names=features,
    )
