import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
import json
from app.config import settings


@contextmanager
def get_conn():
    """Short-lived connection per request. We're not high-traffic enough
    to need a pool for this project — if this were going to prod at scale
    we'd swap this for psycopg_pool, but that's overkill here."""
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS generated_copy (
    cache_key       TEXT PRIMARY KEY,
    product_id      TEXT NOT NULL,
    headline        TEXT,
    subline         TEXT,
    claims_json     JSONB,
    status          TEXT NOT NULL,      -- 'ok' | 'repaired' | 'fallback' | 'rejected'
    attempt_log     JSONB,              -- what happened at each retry, for the review round
    latency_ms      INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_generated_copy_product
    ON generated_copy (product_id, created_at DESC);

CREATE TABLE IF NOT EXISTS eval_runs (
    run_id          TEXT PRIMARY KEY,
    summary_json    JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def init_db():
    with get_conn() as conn:
        conn.execute(SCHEMA)


def make_cache_key(product_id: str, rules_version: str = "v1") -> str:
    # bump rules_version any time brand-rules.json changes meaningfully,
    # so stale copy generated under old rules doesn't get served as "cached"
    import hashlib
    raw = f"{product_id}:{rules_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def save_generated_copy(cache_key: str, product_id: str, headline: str,
                         subline: str, claims: list, status: str,
                         attempt_log: list, latency_ms: int = None,
                         input_tokens: int = None, output_tokens: int = None):
    """Persists one generation result — this is what makes caching
    (from A2's design) actually work: identical requests can be served
    from here instead of re-calling the LLM. Used by Phase D's
    /generate endpoint, not yet wired up until then."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO generated_copy
            (cache_key, product_id, headline, subline, claims_json, status,
             attempt_log, latency_ms, input_tokens, output_tokens)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cache_key) DO UPDATE SET
                headline = EXCLUDED.headline,
                subline = EXCLUDED.subline,
                claims_json = EXCLUDED.claims_json,
                status = EXCLUDED.status,
                attempt_log = EXCLUDED.attempt_log,
                latency_ms = EXCLUDED.latency_ms,
                input_tokens = EXCLUDED.input_tokens,
                output_tokens = EXCLUDED.output_tokens
        """, (cache_key, product_id, headline, subline, json.dumps(claims),
              status, json.dumps(attempt_log), latency_ms, input_tokens, output_tokens))


def get_cached_copy(product_id: str):
    """Fetches the most recent generated copy for a product, if any."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM generated_copy WHERE product_id = %s ORDER BY created_at DESC LIMIT 1",
            (product_id,)
        ).fetchone()
    return dict(row) if row else None


def save_eval_run(run_id: str, summary: dict):
    """Persists a full eval run's summary as JSONB. C5 calls this via
    evaluate.py's run_and_save_eval()."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO eval_runs (run_id, summary_json) VALUES (%s, %s) "
            "ON CONFLICT (run_id) DO UPDATE SET summary_json = EXCLUDED.summary_json",
            (run_id, json.dumps(summary))
        )


def get_eval_run(run_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM eval_runs WHERE run_id = %s", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def get_latest_eval_run():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None