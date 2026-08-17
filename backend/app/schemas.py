from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


# ---- What we force the LLM to produce ----

class Claim(BaseModel):
    """One factual claim in the copy, tied to where it came from.
    Tone/style words ('warm', 'confident') never need one of these —
    only facts do, per the brand rules."""
    text: str
    source_type: Literal["attribute", "review"]
    source_id: str  # e.g. "material" for an attribute, or "R901" for a review


class LLMCopyOutput(BaseModel):
    """The exact shape we ask the model for via tool-calling.
    If the model's response doesn't parse into this, that's already
    a failure the verifier catches in Phase B — not something we
    quietly patch around."""
    headline: str
    subline: str
    claims: list[Claim] = Field(default_factory=list)


# ---- What our API returns to callers ----

class GenerateResponse(BaseModel):
    product_id: str
    headline: str
    subline: str
    claims: list[Claim]
    status: Literal["ok", "repaired", "fallback", "rejected"]
    attempt_log: list[str]
    cached: bool
    latency_ms: int | None = None
    created_at: datetime | None = None


class ProductSummary(BaseModel):
    product_id: str
    name: str
    category: str
    price: float
    has_generated_copy: bool


class EvalProductResult(BaseModel):
    product_id: str
    passed: bool
    status: str
    failed_checks: list[str]


class EvalSummary(BaseModel):
    run_id: str
    total_products: int
    passed: int
    failed: int
    fallback_used: int
    groundedness_pass_rate: float
    details: list[EvalProductResult]
    created_at: datetime