from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import verify_api_key
from app.generate import generate_copy
from app.db import save_generated_copy, get_cached_copy, make_cache_key
from app.data_loader import get_product

router = APIRouter()


@router.post("/generate/{product_id}")
def generate(
    product_id: str,
    force: bool = Query(False, description="Bypass cache and regenerate"),
    _: bool = Depends(verify_api_key),
):
    """Generates (or returns cached) copy for a product. This is the
    expensive endpoint — it may call the LLM up to twice per request —
    so caching is checked FIRST unless force=true is explicitly passed,
    matching the brief's 'identical requests do not regenerate' requirement."""
    product = get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Unknown product_id: {product_id}")

    if not force:
        cached = get_cached_copy(product_id)
        if cached is not None:
            return {
                "product_id": product_id,
                "headline": cached["headline"],
                "subline": cached["subline"],
                "claims": cached["claims_json"],
                "status": cached["status"],
                "attempt_log": cached["attempt_log"],
                "cached": True,
                "latency_ms": cached["latency_ms"],
                "created_at": cached["created_at"].isoformat() if cached["created_at"] else None,
            }

    result = generate_copy(product_id)
    cache_key = make_cache_key(product_id)

    save_generated_copy(
        cache_key=cache_key,
        product_id=product_id,
        headline=result["headline"],
        subline=result["subline"],
        claims=result["claims"],
        status=result["status"],
        attempt_log=result["attempt_log"],
        latency_ms=result["latency_ms"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
    )

    return {**result, "cached": False}


@router.get("/copy/{product_id}")
def get_copy(product_id: str, _: bool = Depends(verify_api_key)):
    """Read-only fetch — never calls the LLM. Returns whatever's
    currently stored for this product, or a clear 404 if nothing has
    been generated yet (distinct from a 404 for an unknown product_id
    entirely — we check that second, more specific case explicitly so
    the error message actually tells the caller which situation they're in)."""
    product = get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Unknown product_id: {product_id}")

    cached = get_cached_copy(product_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail=f"No copy has been generated yet for {product_id}. "
                    f"Call POST /generate/{product_id} first.",
        )

    return {
        "product_id": product_id,
        "headline": cached["headline"],
        "subline": cached["subline"],
        "claims": cached["claims_json"],
        "status": cached["status"],
        "attempt_log": cached["attempt_log"],
        "cached": True,
        "latency_ms": cached["latency_ms"],
        "created_at": cached["created_at"].isoformat() if cached["created_at"] else None,
    }