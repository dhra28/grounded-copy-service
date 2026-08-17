import json
from app.evaluate import build_readable_report

with open("eval_output.json") as f:
    summary = json.load(f)

report = build_readable_report(summary)
print(report)

with open("eval_report.txt", "w") as f:
    f.write(report)
print("\n\nSaved to eval_report.txt")