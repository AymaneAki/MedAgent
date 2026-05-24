from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from tools.pdf_reader import read_report
from tools.threshold_checker import check, check_all
report_path=root / "data" / "reports" / "report_01.txt"

print("=== Test PDF Reader ===")
text = read_report(report_path)
print(text[:200])
print()

print("=== Test check() — single value ===")
result = check("potassium", 6.8, gender="male")
print(result)
print()

print("=== Test check() — normal value ===")
result = check("glucose", 5.0)
print(result)
print()

print("=== Test check_all() — list of values ===")
params = [
    {"parameter": "hemoglobine", "value": 6.8},
    {"parameter": "potassium",   "value": 6.8},
    {"parameter": "sodium",      "value": 128},
    {"parameter": "creatinine",  "value": 520},
]
results = check_all(params, gender="male")
for r in results:
    print(f"  {r['parameter']:<25} {r['value']} {r['unit']:<10} → {r['status']}")