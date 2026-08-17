from app.groundedness import run_groundedness_check
from app.evidence import get_evidence_for

# Real evidence for P105, exactly as the model saw it
evidence = get_evidence_for("P105")

# --- CASE 1: The real, mostly-correct output from our B3 test ---
# Citations are genuine here, so this should PASS.
good_output = {
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

print("=== CASE 1: Genuine claims (should PASS) ===")
result1 = run_groundedness_check(good_output, evidence)
print("Passed:", result1.passed)
for f in result1.failed_claims:
    print(" -", f)
print()

# --- CASE 2: Deliberately broken, three different ways ---
bad_output = {
    "headline": "Doctor-recommended daily gummies",
    "subline": "Cures fatigue and boosts energy every single day.",
    "claims": [
        # 1. Fabricated attribute — P105 has no "clinically_tested" attribute
        {"text": "doctor-recommended", "source_type": "attribute", "source_id": "clinically_tested"},
        # 2. Fabricated / excluded review ID — R911 was filtered out in B1
        {"text": "cures fatigue", "source_type": "review", "source_id": "R911"},
        # 3. Real review ID, but exaggerated claim R912 never actually said
        {"text": "boosts energy every single day", "source_type": "review", "source_id": "R912"},
    ],
}

print("=== CASE 2: Broken claims (should FAIL, all 3 ways) ===")
result2 = run_groundedness_check(bad_output, evidence)
print("Passed:", result2.passed)
for f in result2.failed_claims:
    print(" -", f)