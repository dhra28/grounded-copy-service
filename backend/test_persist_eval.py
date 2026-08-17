from app.db import init_db
from app.evaluate import run_and_save_eval, load_latest_eval, load_eval_by_id
import json

# Make sure tables exist (safe no-op if they already do, per A2's design)
init_db()

print("Running full eval and saving to Postgres...")
print("(this takes ~2-3 minutes due to rate-limit pacing)\n")

summary = run_and_save_eval()
print(f"Saved eval run: {summary['run_id']}")
print(f"Passed: {summary['passed']}/{summary['total_products']}\n")

print("=== Reading back via load_latest_eval() ===")
latest = load_latest_eval()
print("Same run_id as what we just saved?", latest["run_id"] == summary["run_id"])
print("Type of returned summary:", type(latest))

print("\n=== Reading back via load_eval_by_id() ===")
by_id = load_eval_by_id(summary["run_id"])
print("Matches?", by_id["run_id"] == summary["run_id"])

print("\n=== Reading back a fake/nonexistent run_id ===")
missing = load_eval_by_id("this-id-does-not-exist")
print("Correctly returned None?", missing is None)