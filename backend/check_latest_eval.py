from app.evaluate import load_latest_eval

summary = load_latest_eval()
for d in summary["details"]:
    if not d["overall_passed"] or not d["checks"]["groundedness_passed"]:
        print(f"{d['product_id']}: status={d['status']}")
        print("attempt_log:", d["attempt_log"])
        print("structural_failures:", d["checks"]["structural_failures"])
        print("compliance_failures:", d["checks"]["compliance_failures"])
        print("groundedness_failures:", d["checks"]["groundedness_failures"])
        print()