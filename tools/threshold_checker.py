import json
import os

_THRESHOLDS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "thresholds.json"
)

with open(_THRESHOLDS_PATH, "r", encoding="utf-8") as f:
    _DATA = json.load(f)

# Flatten all categories into one lookup dict
# key = parameter name (lowercase, no accents)
_THRESHOLDS: dict = {}
for category in _DATA:
    if category == "_metadata":
        continue
    for param_key, param_data in _DATA[category].items():
        _THRESHOLDS[param_key] = param_data

_ALIASES = {
    "créatinine": "creatinine",
    "hématocrite": "hematocrite",
    "hémoglobine": "hemoglobine",
    "glycémie": "glucose",
    "glycemie": "glucose",
    "natrémie": "sodium",
    "kaliémie": "potassium",
    "chlorémie": "chlore"
}


def _get_normal_range(param_data: dict, gender: str = "default") -> tuple:
    """Returns (min, max) for the given gender or default."""
    normal = param_data["normal"]
    if param_data.get("gender_specific") and gender in normal:
        return normal[gender]["min"], normal[gender]["max"]
    if "default" in normal:
        return normal["default"]["min"], normal["default"]["max"]
    return normal["min"], normal["max"]


def check(parameter: str, value: float, gender: str = "default") -> dict:
    """
    Checks a single biological value against reference thresholds.

    Args:
        parameter : parameter name (e.g. "hemoglobine", "potassium")
        value     : numerical value
        gender    : "male" | "female" | "default"

    Returns a dict:
        {
            "parameter"    : str,
            "value"        : float,
            "unit"         : str,
            "normal_range" : "min–max",
            "status"       : "NORMAL" | "ABNORMAL" | "CRITICAL",
            "clinical_risk": str or None
        }
    """
    key = parameter.lower().strip()
    key = _ALIASES.get(key, key)

    if key not in _THRESHOLDS:
        return {
            "parameter": parameter,
            "value": value,
            "unit": "unknown",
            "normal_range": "N/A",
            "status": "UNKNOWN",
            "clinical_risk": "Parameter not found in reference database"
        }

    ref = _THRESHOLDS[key]
    normal_min, normal_max = _get_normal_range(ref, gender)
    critical_low  = ref.get("critical_low")
    critical_high = ref.get("critical_high")

    # Determine status
    if (critical_low  is not None and value < critical_low) or \
       (critical_high is not None and value > critical_high):
        status = "CRITICAL"
        risk_key = "critical_low" if (critical_low and value < critical_low) \
                   else "critical_high"
        clinical_risk = ref.get(
            "clinical_risk_low" if risk_key == "critical_low" else "clinical_risk_high",
            "Valeur critique — évaluation urgente requise"
        )

    elif value < normal_min or value > normal_max:
        status = "ABNORMAL"
        clinical_risk = ref.get(
            "clinical_risk_low" if value < normal_min else "clinical_risk_high",
            "Valeur anormale"
        )

    else:
        status = "NORMAL"
        clinical_risk = None

    return {
        "parameter"    : ref.get("label", parameter),
        "value"        : value,
        "unit"         : ref.get("unit", ""),
        "normal_range" : f"{normal_min}–{normal_max}",
        "status"       : status,
        "clinical_risk": clinical_risk
    }


def check_all(parameters: list, gender: str = "default") -> list:
    """
    Runs check() on a list of extracted parameters.

    Args:
        parameters: list of dicts with keys: parameter, value
        gender: "male" | "female" | "default"

    Returns list of enriched dicts with status and clinical_risk added.
    """
    results = []
    for item in parameters:
        try:
            result = check(
                parameter=item["parameter"],
                value=float(item["value"]),
                gender=gender
            )
            results.append(result)
        except (KeyError, ValueError) as e:
            results.append({
                "parameter": item.get("parameter", "unknown"),
                "value": item.get("value", None),
                "unit": "unknown",
                "normal_range": "N/A",
                "status": "ERROR",
                "clinical_risk": f"Could not process: {str(e)}"
            })
    return results