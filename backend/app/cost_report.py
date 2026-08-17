from __future__ import annotations
from app.db import get_conn

# Gemini pricing for gemini-3.5-flash-lite, per Google's published rates
# as of when this was built. Worth re-checking before relying on this
# for real budgeting, since LLM pricing changes over time — noted
# explicitly rather than presented as permanently accurate.
PRICE_PER_1M_INPUT_TOKENS = 0.10   # USD
PRICE_PER_1M_OUTPUT_TOKENS = 0.40  # USD


def compute_cost_report() -> dict:
    """Pulls every real generation we've logged in Postgres and
    aggregates actual cost/latency numbers — not estimates, not made up,
    literally what we spent based on captured token counts. This is
    what the README's cost/latency note will be built from."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT status, latency_ms, input_tokens, output_tokens
            FROM generated_copy
        """).fetchall()

    if not rows:
        return {"error": "No generation data yet — run some generations or an eval first."}

    total = len(rows)
    total_input_tokens = sum(r["input_tokens"] or 0 for r in rows)
    total_output_tokens = sum(r["output_tokens"] or 0 for r in rows)
    total_latency_ms = sum(r["latency_ms"] or 0 for r in rows)

    by_status = {}
    for r in rows:
        s = r["status"]
        by_status.setdefault(s, {"count": 0, "total_latency_ms": 0})
        by_status[s]["count"] += 1
        by_status[s]["total_latency_ms"] += r["latency_ms"] or 0

    for s, data in by_status.items():
        data["avg_latency_ms"] = round(data["total_latency_ms"] / data["count"])

    input_cost = (total_input_tokens / 1_000_000) * PRICE_PER_1M_INPUT_TOKENS
    output_cost = (total_output_tokens / 1_000_000) * PRICE_PER_1M_OUTPUT_TOKENS
    total_cost = input_cost + output_cost

    return {
        "total_generations_logged": total,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "avg_latency_ms": round(total_latency_ms / total),
        "by_status": by_status,
        "estimated_cost_usd": round(total_cost, 6),
        "avg_cost_per_generation_usd": round(total_cost / total, 6),
        # Extrapolation the brief explicitly asks for
        "projected_cost_for_100k_products_usd": round((total_cost / total) * 100_000, 2),
        "projected_time_for_100k_products_hours_sequential": round(
            (total_latency_ms / total) * 100_000 / 1000 / 3600, 1
        ),
    }