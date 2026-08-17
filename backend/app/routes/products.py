from __future__ import annotations
from fastapi import APIRouter, Depends

from app.auth import verify_api_key
from app.data_loader import load_products
from app.db import get_cached_copy

router = APIRouter()


@router.get("/products")
def list_products(_: bool = Depends(verify_api_key)):
    """Lists all products from the starter data, each flagged with
    whether copy has already been generated for it. Read-only, no LLM
    calls — but does one Postgres lookup per product to check the cache,
    which is fine at 18 products; at real scale this would need a single
    JOIN-style query instead of N individual lookups, worth flagging."""
    products = load_products()

    result = []
    for product_id, product in products.items():
        cached = get_cached_copy(product_id)
        result.append({
            "product_id": product_id,
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "has_generated_copy": cached is not None,
            "current_status": cached["status"] if cached else None,
        })

    return {"total": len(result), "products": result}