from app.config import settings
print("MODEL VALUE IS:", repr(settings.llm_model))
from app.llm_client import call_llm
import json

result, evidence = call_llm("P105")

print("=== SUCCESS? ===")
print(result.success)
print()

print("=== ERROR (if any) ===")
print(result.error)
print()

print("=== RAW OUTPUT FROM MODEL ===")
print(json.dumps(result.raw_output, indent=2))
print()

print("=== USABLE REVIEWS MODEL SAW ===")
print(json.dumps(evidence["usable_reviews"], indent=2, default=str))
print()

print("=== EXCLUDED REVIEWS (should include R911, the health claim) ===")
print(json.dumps(evidence["excluded_reviews"], indent=2, default=str))
print()

print(f"Latency: {result.latency_ms}ms | Input tokens: {result.input_tokens} | Output tokens: {result.output_tokens}")