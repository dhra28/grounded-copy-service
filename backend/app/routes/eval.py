from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException

from app.auth import verify_api_key
from app.evaluate import run_and_save_eval, load_latest_eval, load_eval_by_id

router = APIRouter()


@router.post("/eval/run")
def trigger_eval(_: bool = Depends(verify_api_key)):
    """Runs the full 18-product eval synchronously and saves it. This
    is a SLOW endpoint by design (~2-3 min due to rate-limit pacing) —
    worth noting in the README rather than hiding, since a caller
    hitting this expects a long wait, not a hung connection. A more
    production-shaped version would make this async with a job ID and
    a polling endpoint; kept synchronous here since 18 products is a
    small, bounded, known-size job for this project's scope."""
    summary = run_and_save_eval()
    return {
        "run_id": summary["run_id"],
        "total_products": summary["total_products"],
        "passed": summary["passed"],
        "failed": summary["failed"],
        "repaired_count": summary["repaired_count"],
        "fallback_used": summary["fallback_used"],
        "groundedness_pass_rate": summary["groundedness_pass_rate"],
    }


@router.get("/eval/results")
def get_latest_results(_: bool = Depends(verify_api_key)):
    """Read-only, fast — returns the most recently saved eval run in
    full detail, no LLM calls. This is what a reviewer hits to actually
    inspect results without waiting for a fresh run."""
    summary = load_latest_eval()
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="No eval run has been performed yet. Call POST /eval/run first.",
        )
    return summary


@router.get("/eval/results/{run_id}")
def get_results_by_id(run_id: str, _: bool = Depends(verify_api_key)):
    """Fetch a SPECIFIC historical run by ID, not just the latest —
    useful once multiple eval runs exist (e.g. before/after a prompt
    change) and you want to compare a specific past result rather than
    only ever seeing the newest one."""
    summary = load_eval_by_id(run_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"No eval run found with id: {run_id}")
    return summary

from app.cost_report import compute_cost_report

@router.get("/eval/cost-report")
def get_cost_report(_: bool = Depends(verify_api_key)):
    """Aggregate cost/latency numbers computed from real logged
    generations — not estimates. See README for the full cost/latency
    discussion this data feeds into."""
    return compute_cost_report()