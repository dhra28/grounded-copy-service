"""Runs the real generate_copy() pipeline against synthetic edge cases.
Monkey-patches the data loader's cache so synthetic products/reviews are
visible to the pipeline for this run only — doesn't touch the real
data/*.json files at all."""
import json
from app import data_loader
from synthetic_data import SYNTHETIC_PRODUCTS, SYNTHETIC_REVIEWS

# Merge synthetic data into the loader's cache temporarily
real_products = data_loader.load_products()
real_reviews = data_loader.load_reviews()

merged_products = {**real_products, **{p["product_id"]: p for p in SYNTHETIC_PRODUCTS}}
merged_reviews = {**real_reviews}
for r in SYNTHETIC_REVIEWS:
    merged_reviews.setdefault(r["product_id"], []).append(r)

data_loader.load_products.cache_clear()
data_loader.load_reviews.cache_clear()
data_loader.load_products = lambda: merged_products
data_loader.load_reviews = lambda: merged_reviews

from app.generate import generate_copy

print("=== SYNTHETIC EDGE CASE TESTS ===\n")
print("SYN001 — wrong-product review (mug, but review talks about a laptop bag)")
r1 = generate_copy("SYN001")
print(json.dumps(r1, indent=2))
print()

print("SYN002 — non-English review (Spanish, about a candle's scent)")
r2 = generate_copy("SYN002")
print(json.dumps(r2, indent=2))
print()

print("SYN003 — review contradicts hard spec (65W claimed, spec says 20W)")
r3 = generate_copy("SYN003")
print(json.dumps(r3, indent=2))