from __future__ import annotations
from app.llm_client import call_llm
from app.verify import run_structural_checks
from app.groundedness import run_groundedness_check
from app.compliance import run_compliance_checks
from app.data_loader import load_brand_rules


def _verify_all(raw_output: dict, evidence: dict) -> tuple[bool, list[str]]:
    """Runs all three verification layers and merges their failures into
    one flat list of human-readable reasons. Order is deliberate: cheapest
    checks first (structural is pure code), most expensive last (groundedness
    involves an LLM call) — if structure already failed, there's no point
    spending an LLM call checking groundedness of malformed output."""
    reasons = []

    structural = run_structural_checks(raw_output)
    if not structural.passed:
        reasons.extend(structural.failed_checks)
        # don't bother with groundedness/compliance if structure itself
        # is broken — headline/subline may not even exist to check
        return False, reasons

    compliance = run_compliance_checks(raw_output)
    reasons.extend(compliance.issues)

    grounded = run_groundedness_check(raw_output, evidence)
    if not grounded.passed:
        reasons.extend([
            f"Unsupported claim '{f['claim_text']}' (cited {f['source_id']}): {f['reason']}"
            for f in grounded.failed_claims
        ])

    passed = len(reasons) == 0
    return passed, reasons


def _build_fallback_copy(evidence: dict) -> dict:
    """Deterministic, LLM-free, template-based copy. This is the safety
    net: it can ALWAYS run, always complies (we wrote the wording), and
    always cites real attributes only — because we control every word,
    there's nothing to hallucinate. Deliberately plain rather than
    creative; per the brief, generic-but-honest beats invented-but-wrong."""
    product = evidence["product"]
    name = product["name"]
    category = product["category"]
    attributes = product.get("attributes", {})

    claims = []
    facts = []

    # pull at most 2 attribute facts into plain, factual phrases —
    # keeping it short and dumb on purpose, since this path exists to
    # be safe, not clever
    for key, value in list(attributes.items())[:2]:
        if isinstance(value, bool):
            phrase = key.replace("_", " ")
        elif isinstance(value, list):
            phrase = f"{key.replace('_', ' ')}: {', '.join(str(v) for v in value)}"
        else:
            phrase = f"{key.replace('_', ' ')}: {value}"
        facts.append(phrase)
        claims.append({"text": phrase, "source_type": "attribute", "source_id": key})

    if facts:
        headline = f"{name}"[:60]
        subline = f"{', '.join(facts)}."[:120]
    else:
        # zero attributes AND presumably zero usable reviews too —
        # the absolute floor case (e.g. the plain tee with attributes: {})
        headline = f"{name}"[:60]
        subline = f"A dependable choice in {category.lower()}."[:120]

    return {"headline": headline, "subline": subline, "claims": claims}


def generate_copy(product_id: str) -> dict:
    """The full B7 pipeline. Returns a dict matching GenerateResponse's
    shape (minus cached/created_at, which the API layer in Phase D adds
    from the DB row). This function has NO knowledge of caching or
    Postgres — that's D's job — it only knows how to produce one
    verified result for one product_id, which keeps it testable in
    isolation exactly like we've been doing all along."""
    attempt_log = []

    # --- Attempt 1 ---
    result1, evidence = call_llm(product_id)
    attempt_log.append(f"Attempt 1: LLM call {'succeeded' if result1.success else 'FAILED: ' + str(result1.error)}")

    if result1.success:
        passed1, reasons1 = _verify_all(result1.raw_output, evidence)
        attempt_log.append(f"Attempt 1 verification: {'PASSED' if passed1 else 'FAILED - ' + '; '.join(reasons1)}")

        if passed1:
            return {
                "product_id": product_id,
                "headline": result1.raw_output["headline"],
                "subline": result1.raw_output["subline"],
                "claims": result1.raw_output["claims"],
                "status": "ok",
                "attempt_log": attempt_log,
                "latency_ms": result1.latency_ms,
                "input_tokens": result1.input_tokens,
                "output_tokens": result1.output_tokens,
            }

        # --- Attempt 2: repair, feeding back exactly what failed ---
        feedback = "; ".join(reasons1)
        result2, evidence2 = call_llm(product_id, retry_feedback=feedback)
        attempt_log.append(f"Attempt 2: LLM call {'succeeded' if result2.success else 'FAILED: ' + str(result2.error)}")

        if result2.success:
            passed2, reasons2 = _verify_all(result2.raw_output, evidence2)
            attempt_log.append(f"Attempt 2 verification: {'PASSED' if passed2 else 'FAILED - ' + '; '.join(reasons2)}")

            if passed2:
                return {
                    "product_id": product_id,
                    "headline": result2.raw_output["headline"],
                    "subline": result2.raw_output["subline"],
                    "claims": result2.raw_output["claims"],
                    "status": "repaired",
                    "attempt_log": attempt_log,
                    "latency_ms": result1.latency_ms + result2.latency_ms,
                    "input_tokens": result1.input_tokens + result2.input_tokens,
                    "output_tokens": result1.output_tokens + result2.output_tokens,
                }

    # --- Fallback: both attempts failed (or attempt 1's call itself failed) ---
    fallback_copy = _build_fallback_copy(evidence)
    attempt_log.append("Fallback: used deterministic attribute-only template")

    return {
        "product_id": product_id,
        "headline": fallback_copy["headline"],
        "subline": fallback_copy["subline"],
        "claims": fallback_copy["claims"],
        "status": "fallback",
        "attempt_log": attempt_log,
        "latency_ms": result1.latency_ms,
        "input_tokens": result1.input_tokens,
        "output_tokens": result1.output_tokens,
    }