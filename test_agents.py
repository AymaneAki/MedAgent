# test_agents.py

from tools.pdf_reader import read_report
from agents import (
    agent_extractor,
    agent_interpreter,
    agent_alerter,
    agent_writer
)
import json

print("📄 Reading report...")
report_text = read_report("data/reports/report_01.txt")

print("\n🔍 Agent 1 — Extracting parameters...")
extracted = agent_extractor.run(report_text)
print(f"   → {len(extracted)} parameters extracted")
for p in extracted:
    print(f"      {p['parameter']:<25} {p['value']} {p['unit']}")

print("\n🧪 Agent 2 — Interpreting values...")
annotated = agent_interpreter.run(extracted, gender="male")
print(f"   → {len(annotated)} parameters annotated")
for p in annotated:
    status_icon = "🔴" if p["status"] == "CRITICAL" else \
                  "🟡" if p["status"] == "ABNORMAL" else "🟢"
    print(f"      {status_icon} {p['parameter']:<25} → {p['status']}")

print("\n🚨 Agent 3 — Generating alerts...")
alert_report = agent_alerter.run(annotated)
print(f"   → {alert_report['critical_count']} critical / "
      f"{alert_report['abnormal_count']} abnormal")

print("\n📋 Agent 4 — Writing summary...")
summary = agent_writer.run(annotated, alert_report, report_text)
print("\n" + "="*60)
print(summary)
print("="*60)