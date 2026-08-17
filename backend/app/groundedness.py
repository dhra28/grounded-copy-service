from __future__ import annotations
import time
import json
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from app.config import settings
from app.llm_client import _extract_retry_delay

genai.configure(api_key=settings.gemini_api_key)


class GroundednessResult:
    def __init__(self, passed: bool, failed_claims: list[dict]):
        self.passed = passed
        self.failed_claims = failed_claims  # list of {claim_text, source_id, reason}


def _check_attribute_claims(claims: list[dict], product: dict) -> list[dict]:
    """Deterministic, no LLM needed. An attribute claim is only as good
    as whether the source_id actually exists on the product — if the
    model cites 'material' but the product has no 'material' attribute,
    that's a fabricated citation, catchable with zero ambiguity."""
    failures = []
    attributes = product.get("attributes", {})

    for c in claims:
        if c.get("source_type") != "attribute":
            continue
        source_id = c.get("source_id")
        if source_id not in attributes:
            failures.append({
                "claim_text": c.get("text"),
                "source_id": source_id,
                "reason": f"Cited attribute '{source_id}' does not exist on this product",
            })

    return failures


def _check_review_claims_deterministic(claims: list[dict], usable_reviews: list[dict]) -> tuple[list[dict], list[dict]]:
    """First pass, still no LLM: does the cited review_id even exist in
    the usable set? Catches fabricated review IDs and — importantly —
    catches a model citing an EXCLUDED review (e.g. R911) that slipped
    through some other way. Returns (hard_failures, claims_needing_llm_check)."""
    valid_ids = {r["review_id"] for r in usable_reviews}
    reviews_by_id = {r["review_id"]: r for r in usable_reviews}

    hard_failures = []
    needs_llm_check = []

    for c in claims:
        if c.get("source_type") != "review":
            continue
        source_id = c.get("source_id")
        if source_id not in valid_ids:
            hard_failures.append({
                "claim_text": c.get("text"),
                "source_id": source_id,
                "reason": f"Cited review '{source_id}' is not in the usable review set "
                          f"(fabricated ID or an excluded/filtered review)",
            })
        else:
            needs_llm_check.append({
                "claim_text": c.get("text"),
                "source_id": source_id,
                "review_text": reviews_by_id[source_id]["text"],
            })

    return hard_failures, needs_llm_check


JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "source_id": {"type": "string"},
                    "supported": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["claim_text", "source_id", "supported", "reason"],
            },
        }
    },
    "required": ["results"],
}


def _llm_judge_review_claims(items: list[dict]) -> list[dict]:
    """One batched call for ALL review-backed claims in a generation,
    not one call per claim — keeps groundedness-check cost proportional
    to products, not to claims, which matters directly for the
    '100k products' cost question.

    Now includes a 2-attempt retry specifically for 429 (rate limit)
    errors, mirroring llm_client.py's call_llm(). This was added after
    a real eval run showed a judge-call 429 being treated as a hard
    failure with zero retry, incorrectly marking genuinely-valid claims
    as unsupported just because the judge itself couldn't be reached —
    a false negative on groundedness caused by infrastructure, not by
    an actual grounding problem."""
    if not items:
        return []

    prompt = (
        "You are a strict fact-checker. For each claim below, decide if the "
        "cited review text actually supports the claim. A claim is SUPPORTED "
        "only if the review genuinely says this — not if it's merely plausible "
        "or similar in spirit. Be strict about exaggeration: if the claim adds "
        "certainty, degree, or specifics the review didn't state, mark it NOT supported.\n\n"
        f"{json.dumps(items, indent=2)}\n\n"
        "Respond with a JSON object matching the schema: for each item, whether "
        "it is supported, and a one-sentence reason."
    )

    model = genai.GenerativeModel(
        model_name=settings.llm_model.strip(),
        generation_config=genai.GenerationConfig(
            max_output_tokens=1500,
            temperature=0.0,  # judge should be deterministic, not creative
            response_mime_type="application/json",
            response_schema=JUDGE_SCHEMA,
        ),
    )

    last_error = None
    for attempt in range(2):
        try:
            response = model.generate_content(
                prompt, request_options={"timeout": settings.llm_timeout_seconds}
            )
            parsed = json.loads(response.text)
            return parsed.get("results", [])
        except ResourceExhausted as e:
            wait_s = _extract_retry_delay(str(e))
            last_error = str(e)
            if attempt == 0:  # only wait if we're going to try again
                time.sleep(wait_s)
        except Exception as e:
            # non-429 errors: no point retrying identically, fail straight away
            last_error = str(e)
            break

    # If the judge call itself fails even after retry, we can't silently
    # assume everything passed — that would defeat the purpose. Treat
    # every item as unverified/failed instead, forcing a repair or
    # fallback rather than shipping unverified claims.
    return [
        {
            "claim_text": item["claim_text"],
            "source_id": item["source_id"],
            "supported": False,
            "reason": f"Groundedness judge call failed after retry: {last_error}",
        }
        for item in items
    ]


def run_groundedness_check(raw_output: dict, evidence: dict) -> GroundednessResult:
    """Entry point B7/C1 call. Combines the deterministic attribute check,
    the deterministic review-ID check, and the LLM-judge check for the
    review claims that pass the ID check — three layers, cheapest and
    most certain checks run first, LLM only used for what genuinely
    needs semantic judgment."""
    claims = raw_output.get("claims", [])
    product = evidence["product"]
    usable_reviews = evidence["usable_reviews"]

    attribute_failures = _check_attribute_claims(claims, product)
    review_hard_failures, needs_llm_check = _check_review_claims_deterministic(claims, usable_reviews)

    judge_results = _llm_judge_review_claims(needs_llm_check)
    llm_failures = [
        {
            "claim_text": r["claim_text"],
            "source_id": r["source_id"],
            "reason": r["reason"],
        }
        for r in judge_results
        if not r.get("supported", False)
    ]

    all_failures = attribute_failures + review_hard_failures + llm_failures
    return GroundednessResult(passed=len(all_failures) == 0, failed_claims=all_failures)