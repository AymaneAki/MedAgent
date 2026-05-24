# agents/writer_agent.py

import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
from llm.model import call_llm
from config.prompt_loader import load_prompt

def run(annotated_params: list, alert_report: dict, report_text: str) -> str:
    critical_alerts = [a for a in alert_report.get("alerts", []) if a["urgency"] == "HIGH"]
    abnormal_alerts = [a for a in alert_report.get("alerts", []) if a["urgency"] == "MEDIUM"]

    critical_str = "\n".join([
        f"- {a['parameter']}: {a['value']} {a['unit']} "
        f"(normal: {a['normal_range']}) → {a['clinical_risk']}"
        for a in critical_alerts
    ]) or "None"

    abnormal_str = "\n".join([
        f"- {a['parameter']}: {a['value']} {a['unit']} "
        f"(normal: {a['normal_range']})"
        for a in abnormal_alerts
    ]) or "None"

    actions_str = "\n".join([
        f"- [{a['urgency']}] {a['parameter']}: {a['action']}"
        for a in alert_report.get("alerts", [])
    ]) or "None"

    template = load_prompt("writer")
    prompt   = template.format(
        critical_str  = critical_str,
        abnormal_str  = abnormal_str,
        actions_str   = actions_str,
        report_excerpt= report_text[:800]
    )

    return call_llm(prompt, max_tokens=700, temperature=0.2)