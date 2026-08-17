from app.compliance import run_compliance_checks

# Case 1: Clean copy, no superlatives — should PASS
clean = {
    "headline": "Berry vegan gummies for your daily routine",
    "subline": "60 gummies with great taste, easy to fit into your morning.",
}
print("=== CASE 1: Clean (should PASS) ===")
result1 = run_compliance_checks(clean)
print("Passed:", result1.passed, "| Issues:", result1.issues)
print()

# Case 2: Contains an unverifiable superlative — should FAIL
puffed_up = {
    "headline": "The ultimate pillow for perfect sleep",
    "subline": "World-class comfort, unmatched by any competitor.",
}
print("=== CASE 2: Superlative-heavy (should FAIL) ===")
result2 = run_compliance_checks(puffed_up)
print("Passed:", result2.passed, "| Issues:", result2.issues)
print()

# Case 3: Borderline — "top" alone should NOT trip it (only "top-rated" should)
borderline = {
    "headline": "Sits on top of your nightstand easily",
    "subline": "A great addition to your bedside setup.",
}
print("=== CASE 3: Borderline, false-positive check (should PASS) ===")
result3 = run_compliance_checks(borderline)
print("Passed:", result3.passed, "| Issues:", result3.issues)