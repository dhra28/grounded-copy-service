from app.verify import run_structural_checks

# This is the EXACT output we got from the real P105 test in B3 —
# the one with the uncited "immune support" bug.
buggy_output = {
    "headline": "Berry vegan immune support gummies",
    "subline": "Sixty tasty berry gummies that fit right into your morning routine.",
    "claims": [
        {"text": "berry", "source_type": "attribute", "source_id": "flavour"},
        {"text": "vegan", "source_type": "attribute", "source_id": "vegan"},
        {"text": "60", "source_type": "attribute", "source_id": "count"},
        {"text": "Taste great", "source_type": "review", "source_id": "R912"},
        {"text": "Easy part of my morning routine", "source_type": "review", "source_id": "R912"},
    ],
}

print("=== TEST 1: Buggy output (should FAIL) ===")
result = run_structural_checks(buggy_output)
print("Passed:", result.passed)
print("Failed checks:")
for f in result.failed_checks:
    print(" -", f)
print()

# A clean, compliant example — should pass everything
clean_output = {
    "headline": "Berry vegan gummies for your daily routine",
    "subline": "60 gummies with great taste, easy to fit into your morning.",
    "claims": [
        {"text": "berry", "source_type": "attribute", "source_id": "flavour"},
        {"text": "vegan", "source_type": "attribute", "source_id": "vegan"},
        {"text": "60", "source_type": "attribute", "source_id": "count"},
        {"text": "great taste", "source_type": "review", "source_id": "R912"},
        {"text": "easy to fit into your morning", "source_type": "review", "source_id": "R912"},
    ],
}

print("=== TEST 2: Clean output (should PASS) ===")
result2 = run_structural_checks(clean_output)
print("Passed:", result2.passed)
print("Failed checks:", result2.failed_checks)
print()

# A deliberately broken structure — missing subline entirely
broken_output = {
    "headline": "Some headline",
    "claims": [],
}

print("=== TEST 3: Broken structure (should FAIL, structure check) ===")
result3 = run_structural_checks(broken_output)
print("Passed:", result3.passed)
print("Failed checks:")
for f in result3.failed_checks:
    print(" -", f)