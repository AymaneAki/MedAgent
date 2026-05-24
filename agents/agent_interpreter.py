# agents/interpreter_agent.py


import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
from tools.threshold_checker import check_all

def run(extracted_params: list, gender: str = "default") -> list:
    if not extracted_params:
        raise ValueError("No parameters received from extractor agent.")
    return check_all(extracted_params, gender=gender)