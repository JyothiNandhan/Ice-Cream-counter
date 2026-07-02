import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from database import (
    get_all_stock, restock_product, full_restock_all,
    add_restock_log, get_restock_log, get_stock_by_product,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stock", tags=["stock"])


class RestockRequest(BaseModel):
    units_to_add: int


@router.get("")
def list_stock(username: str = Depends(get_current_user)):
    return {"items": get_all_stock()}


@router.patch("/{product_id}")
def restock_one(product_id: int, body: RestockRequest, username: str = Depends(get_current_user)):
    if body.units_to_add <= 0:
        raise HTTPException(status_code=400, detail="units_to_add must be positive")

    # Look up product name for the log
    all_stock = get_all_stock()
    product = next((p for p in all_stock if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    updated = restock_product(product_id, body.units_to_add)
    add_restock_log(
        performed_by=username,
        action=f"Added {body.units_to_add} units",
        product_id=product_id,
        brand=product["brand"],
        product_name=product["product_name"],
        units_added=body.units_to_add,
    )
    logger.info(f"[Stock] {username} restocked {product['product_name']} +{body.units_to_add}")
    return updated


@router.post("/full-restock")
def do_full_restock(username: str = Depends(get_current_user)):
    full_restock_all()
    add_restock_log(
        performed_by=username,
        action="Full Restock — all products reset to full stock",
        brand="ALL",
        product_name="ALL",
    )
    logger.info(f"[Stock] {username} triggered Full Restock")
    return {"status": "ok", "message": "All products reset to full stock", "items": get_all_stock()}


@router.get("/log")
def get_log(limit: int = 50, username: str = Depends(get_current_user)):
    return {"log": get_restock_log(limit)}
