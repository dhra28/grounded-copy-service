from __future__ import annotations
import time
import uuid
from datetime import datetime, timezone

from app.data_loader import all_product_ids
from app.generate import generate_copy
from app.verify import run_structural_checks
from app.groundedness import run_groundedness_check
from app.compliance import run_compliance_checks
from app.evidence import get_evidence_for
from app.db import save_eval_run, get_latest_eval_run, get_eval_run, save_generated_copy, make_cache_key



def _re_verify_for_reporting(final_output: dict, product_id: str) -> dict:
    """generate_copy() already verifies internally as part of the repair
    ladder — but by the time it returns, we only have the FINAL accepted
    result, not a breakdown of which individual check categories it
    passed. For the eval report we want per-category visibility (did it
    pass length? banned words? groundedness? compliance?) rather than
    just a single pass/fail, so we re-run the checks against the final
    output. This is cheap for structural/compliance (pure code) but
    re-running groundedness means a second LLM judge call per product —
    an honest cost tradeoff worth naming rather than hiding: eval
    accuracy costs roughly 2x the generation cost itself."""
    evidence = get_evidence_for(product_id)
    raw = {"headline": final_output["headline"], "subline": final_output["subline"], "claims": final_output["claims"]}

    structural = run_structural_checks(raw)
    compliance = run_compliance_checks(raw)
    grounded = run_groundedness_check(raw, evidence)

    return {
        "structural_passed": structural.passed,
        "structural_failures": structural.failed_checks,
        "compliance_passed": compliance.passed,
        "compliance_failures": compliance.issues,
        "groundedness_passed": grounded.passed,
        "groundedness_failures": [
            f"{f['claim_text']} (cited {f['source_id']}): {f['reason']}"
            for f in grounded.failed_claims
        ],
    }


def run_full_eval() -> dict:
    """Runs generate_copy() for every product, then re-verifies each
    final result for per-category reporting. Returns the full summary
    dict — Phase D's API layer persists this to Postgres via
    save_eval_run(), this function itself has no DB knowledge, staying
    consistent with generate.py's separation of concerns."""
    run_id = str(uuid.uuid4())
    details = []

    passed_count = 0
    fallback_count = 0
    repaired_count = 0
    groundedness_pass_count = 0

    for product_id in all_product_ids():
        gen_result = generate_copy(product_id)
        checks = _re_verify_for_reporting(gen_result, product_id)
        save_generated_copy(
            cache_key=make_cache_key(product_id),
            product_id=product_id,
            headline=gen_result["headline"],
            subline=gen_result["subline"],
            claims=gen_result["claims"],
            status=gen_result["status"],
            attempt_log=gen_result["attempt_log"],
            latency_ms=gen_result["latency_ms"],
            input_tokens=gen_result["input_tokens"],
            output_tokens=gen_result["output_tokens"],
        )

        # Free-tier Gemini caps at 15 requests/minute. Each product can
        # use up to 3 calls (2 generation attempts + 1 groundedness
        # judge), so without pacing we blow through the quota partway
        # through an 18-product run and silently degrade to fallback
        # for the rest — which LOOKS like "no evidence available" but
        # is actually just throttling. This sleep trades eval speed
        # for eval honesty.
        time.sleep(7)

        overall_passed = checks["structural_passed"] and checks["compliance_passed"]

        if overall_passed:
            passed_count += 1
        if checks["groundedness_passed"]:
            groundedness_pass_count += 1
        if gen_result["status"] == "fallback":
            fallback_count += 1
        if gen_result["status"] == "repaired":
            repaired_count += 1

        details.append({
            "product_id": product_id,
            "status": gen_result["status"],
            "overall_passed": overall_passed,
            "headline": gen_result["headline"],
            "subline": gen_result["subline"],
            "claims": gen_result["claims"],
            "checks": checks,
            "latency_ms": gen_result["latency_ms"],
            "attempt_log": gen_result["attempt_log"],
        })

    total = len(details)
    summary = {
        "run_id": run_id,
        "total_products": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "repaired_count": repaired_count,
        "fallback_used": fallback_count,
        "groundedness_pass_rate": round(groundedness_pass_count / total, 3) if total else 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "details": details,
    }
    return summary

def build_readable_report(summary: dict) -> str:
    """Turns the raw summary dict into a plain-text report — this is
    what gets pasted into the README or printed for a human reviewer,
    separate from the JSON that the API/DB actually stores. Keeping
    this as a pure formatting function (no new computation) means the
    numbers here are guaranteed to match run_full_eval()'s own numbers
    exactly — no risk of a second, drifting calculation."""
    lines = []
    lines.append(f"Eval Run: {summary['run_id']}")
    lines.append(f"Run at: {summary['created_at']}")
    lines.append(f"Total products evaluated: {summary['total_products']}")
    lines.append("")
    lines.append("-- Programmatic checks (structural + compliance) --")
    lines.append(f"Passed: {summary['passed']}/{summary['total_products']}")
    lines.append(f"Failed: {summary['failed']}/{summary['total_products']}")
    lines.append("")
    lines.append("-- Generation pipeline behavior --")
    ok_count = summary['total_products'] - summary['repaired_count'] - summary['fallback_used']
    lines.append(f"First-attempt success: {ok_count}")
    lines.append(f"Required repair (attempt 2): {summary['repaired_count']}")
    lines.append(f"Fell back to deterministic template: {summary['fallback_used']}")
    lines.append("")
    lines.append("-- Groundedness (LLM-judge verified) --")
    lines.append(f"Pass rate: {summary['groundedness_pass_rate'] * 100:.1f}%")
    lines.append("")

    failures = [d for d in summary["details"] if not d["overall_passed"] or not d["checks"]["groundedness_passed"]]
    if failures:
        lines.append("-- Products with issues --")
        for d in failures:
            lines.append(f"  {d['product_id']}: status={d['status']}")
            for f in d["checks"]["structural_failures"] + d["checks"]["compliance_failures"] + d["checks"]["groundedness_failures"]:
                lines.append(f"    - {f}")
    else:
        lines.append("-- No products failed any check. --")

    fallback_products = [d for d in summary["details"] if d["status"] == "fallback"]
    if fallback_products:
        lines.append("")
        lines.append("-- Products that used the fallback template --")
        for d in fallback_products:
            reason = d["attempt_log"][0] if d["attempt_log"] else "unknown"
            lines.append(f"  {d['product_id']}: {reason[:100]}...")

    return "\n".join(lines)

def run_and_save_eval() -> dict:
    """The function Phase D's API endpoint will actually call. Runs the
    full eval, then persists it. Kept separate from run_full_eval()
    itself so the pure computation stays DB-agnostic and independently
    testable — same separation-of-concerns pattern we've used since
    generate.py in B7."""
    summary = run_full_eval()
    save_eval_run(summary["run_id"], summary)
    return summary


def load_latest_eval() -> dict | None:
    """Reads the most recent stored eval run back out of Postgres.
    Returns None if no eval has ever been run — Phase D's endpoint
    needs to handle that case with a clear message, not a crash."""
    row = get_latest_eval_run()
    if row is None:
        return None
    return row["summary_json"]


def load_eval_by_id(run_id: str) -> dict | None:
    row = get_eval_run(run_id)
    if row is None:
        return None
    return row["summary_json"]