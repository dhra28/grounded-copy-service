from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache
def load_products() -> dict[str, dict]:
    with open(DATA_DIR / "products.json") as f:
        products = json.load(f)
    return {p["product_id"]: p for p in products}


@lru_cache
def load_reviews() -> dict[str, list[dict]]:
    with open(DATA_DIR / "reviews.json") as f:
        reviews = json.load(f)

    by_product: dict[str, list[dict]] = {}
    for r in reviews:
        by_product.setdefault(r["product_id"], []).append(r)
    return by_product


@lru_cache
def load_brand_rules() -> dict:
    with open(DATA_DIR / "brand-rules.json") as f:
        return json.load(f)


def get_product(product_id: str) -> dict | None:
    return load_products().get(product_id)


def get_reviews_for(product_id: str) -> list[dict]:
    return load_reviews().get(product_id, [])


def all_product_ids() -> list[str]:
    return list(load_products().keys())