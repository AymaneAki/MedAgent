# agents/alerter_agent.py

import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
from llm.model import call_llm
from config.prompt_loader import load_prompt

ALERT_STATUSES = {"CRITICAL", "ABNORMAL"}
URGENCY_MAP    = {"CRITICAL": "HIGH", "ABNORMAL": "MEDIUM", "UNKNOWN": "LOW"}

def run(annotated_params: list) -> dict:
    flagged = [p for p in annotated_params if p.get("status") in ALERT_STATUSES]

    if not flagged:
        return {"critical_count": 0, "abnormal_count": 0, "alerts": []}

    alerts = []
    for param in flagged:
        action = _get_action(param)
        alerts.append({
            "parameter":     param["parameter"],
            "value":         param["value"],
            "unit":          param["unit"],
            "status":        param["status"],
            "urgency":       URGENCY_MAP.get(param["status"], "LOW"),
            "normal_range":  param.get("normal_range", "N/A"),
            "clinical_risk": param.get("clinical_risk", ""),
            "action":        action
        })

    alerts.sort(key=lambda x: 0 if x["urgency"] == "HIGH" else 1)

    return {
        "critical_count": sum(1 for a in alerts if a["status"] == "CRITICAL"),
        "abnormal_count": sum(1 for a in alerts if a["status"] == "ABNORMAL"),
        "alerts":         alerts
    }


def _get_action(param: dict) -> str:
    template = load_prompt("alerter")
    prompt   = template.format(
        parameter     = param["parameter"],
        value         = param["value"],
        unit          = param["unit"],
        normal_range  = param.get("normal_range", "N/A"),
        status        = param["status"],
        clinical_risk = param.get("clinical_risk", "")
    )
    return call_llm(prompt, max_tokens=80, temperature=0.1).strip()