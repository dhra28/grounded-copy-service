from app.generate import generate_copy
import json

# Try a few different products to see different paths through the ladder:
# P105 - has the health-claim trap, good test of the whole pipeline
# P104 - empty attributes, tests low-evidence handling
# P103 - conflicting reviews, tests the conflict-handling instruction
for product_id in ["P105", "P104", "P103"]:
    print(f"\n{'='*50}")
    print(f"PRODUCT: {product_id}")
    print('='*50)
    result = generate_copy(product_id)
    print(json.dumps(result, indent=2))