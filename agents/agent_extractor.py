# agents/extractor_agent.py

import json
import re
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
from llm.model import call_llm
from config.prompt_loader import load_prompt

def run(report_text: str) -> list:
    template = load_prompt("extractor")
    prompt   = template.format(report_text=report_text)
    raw      = call_llm(prompt, max_tokens=2048, temperature=0.0)
    return _parse_json(raw)


def _parse_json(raw: str) -> list:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    match   = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in LLM output:\n{raw}")
    try:
        data = json.loads(match.group())
        return [
            {
                "parameter":      str(item["parameter"]).lower().strip(),
                "value":          float(item["value"]),
                "unit":           str(item.get("unit", "")).strip().replace("G/LL", "G/L").replace("g/dl", "g/dL"),
                "source_context": str(item.get("source_context", "Extrait du rapport")).strip()
            }
            for item in data
            if "parameter" in item and "value" in item
        ]
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse error: {e}\nRaw:\n{raw}")