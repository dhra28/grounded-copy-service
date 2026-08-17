from app.evaluate import run_full_eval
import json
import time

print("Running full eval across all 18 products — this will take a few minutes...")
start = time.time()

summary = run_full_eval()

elapsed = time.time() - start
print(f"\nDone in {elapsed:.1f} seconds\n")

# Print the top-level numbers first — the headline result
print("=== SUMMARY ===")
print(f"Run ID: {summary['run_id']}")
print(f"Total products: {summary['total_products']}")
print(f"Passed (structural + compliance): {summary['passed']}")
print(f"Failed: {summary['failed']}")
print(f"Repaired (needed attempt 2): {summary['repaired_count']}")
print(f"Fallback used: {summary['fallback_used']}")
print(f"Groundedness pass rate: {summary['groundedness_pass_rate']}")

# Then a compact per-product line so you can scan for anything odd
print("\n=== PER-PRODUCT ===")
for d in summary["details"]:
    flag = "OK" if d["overall_passed"] else "FAIL"
    grounded_flag = "grounded" if d["checks"]["groundedness_passed"] else "NOT GROUNDED"
    print(f"{d['product_id']:6} | {flag:4} | {d['status']:9} | {grounded_flag}")

# Save the full detailed output to a file too, since this is a lot of
# data to read in a terminal — useful for the README/submission later
with open("eval_output.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nFull details written to eval_output.json")