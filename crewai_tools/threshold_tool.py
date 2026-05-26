# crewai_tools/threshold_tool.py
#
# Wraps tools/threshold_checker.py as a CrewAI BaseTool.
# The interpreter agent uses this to classify each extracted parameter.
# Using a tool (not LLM reasoning) keeps classification 100% deterministic.

import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from crewai.tools import BaseTool
from tools.threshold_checker import check, check_all


class ThresholdCheckerTool(BaseTool):
    name: str = "Medical Threshold Checker"
    description: str = (
        "Checks a biological parameter value against standard medical reference ranges. "
        "Classifies the value as NORMAL, ABNORMAL, or CRITICAL. "
        "Input: JSON string with fields: 'parameter' (str), 'value' (float), "
        "'gender' (optional: 'male'|'female'|'default'). "
        "Output: JSON string with status, normal_range, and clinical_risk."
    )

    def _run(self, input_str: str) -> str:
        try:
            data   = json.loads(input_str)
            result = check(
                parameter = data["parameter"],
                value     = float(data["value"]),
                gender    = data.get("gender", "default")
            )
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})


class BulkThresholdCheckerTool(BaseTool):
    name: str = "Bulk Medical Threshold Checker"
    description: str = (
        "Checks a list of biological parameters against medical reference ranges in one call. "
        "Input: JSON string with fields: "
        "'parameters' (list of {parameter, value} dicts), "
        "'gender' (optional: 'male'|'female'|'default'). "
        "Output: JSON array with status and clinical_risk for each parameter."
    )

    def _run(self, input_str: str) -> str:
        try:
            data    = json.loads(input_str)
            results = check_all(
                parameters = data["parameters"],
                gender     = data.get("gender", "default")
            )
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})