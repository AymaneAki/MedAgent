# test/test_medagent.py

import json
import pytest
from pathlib import Path
import sys

# Add project root to path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from tools.threshold_checker import check, check_all
from tools.pdf_reader import read_report
from llm.fallback import fallback_call_llm
from agents import agent_extractor, agent_interpreter, agent_alerter, agent_writer

def test_threshold_checker_normal():
    # Glucose normal is 3.9 to 6.1 mmol/L
    res = check("glucose", 5.0)
    assert res["status"] == "NORMAL"
    assert res["parameter"] == "Glycémie (à jeun)"
    assert res["unit"] == "mmol/L"
    assert res["clinical_risk"] is None

def test_threshold_checker_abnormal():
    # Sodium normal is 136 to 145 mmol/L. 128 is below normal but above critical (120).
    res = check("sodium", 128.0)
    assert res["status"] == "ABNORMAL"
    assert res["clinical_risk"] is not None

def test_threshold_checker_critical():
    # Hemoglobine critical low is 7.0 g/dL
    res = check("hemoglobine", 6.8, gender="male")
    assert res["status"] == "CRITICAL"
    assert "Anémie" in res["clinical_risk"]

def test_pdf_reader_txt():
    report_path = root / "data" / "reports" / "report_01.txt"
    text = read_report(str(report_path))
    assert "RAPPORT BIOLOGIQUE" in text
    assert "Hémoglobine : 6.8 g/dL" in text

def test_fallback_extractor_llm():
    # Mock a prompt for extractor
    prompt = """
    You are a meticulous medical data extractor. Your ONLY job is to extract biological parameters.
    REPORT:
    Hémoglobine : 6.8 g/dL
    Sodium : 128.0 mmol/L
    """
    raw_json = fallback_call_llm(prompt)
    data = json.loads(raw_json)
    
    assert len(data) == 2
    assert data[0]["parameter"] == "hemoglobine"
    assert data[0]["value"] == 6.8
    assert data[0]["unit"] == "g/dL"
    
    assert data[1]["parameter"] == "sodium"
    assert data[1]["value"] == 128.0
    assert data[1]["unit"] == "mmol/L"

def test_fallback_alerter_llm():
    prompt = """
    You are an emergency physician analyzing a critical lab result.
    Parameter : hemoglobine
    Value     : 6.8 g/dL
    Status    : CRITICAL
    Risk      : Anémie sévère
    Action:
    """
    action = fallback_call_llm(prompt)
    assert "Transfusion" in action

def test_fallback_writer_llm():
    prompt = """
    You are a medical report writer.
    CRITICAL VALUES:
    - hemoglobine: 6.8 g/dL (normal: 13.5-17.5) → Anémie sévère
    ABNORMAL VALUES:
    - sodium: 128 mmol/L
    SUGGESTED ACTIONS FROM ANALYSIS:
    - [HIGH] hemoglobine: Transfusion
    ORIGINAL REPORT EXCERPT:
    Âge : 67 ans
    Sexe : Masculin
    Motif : Fatigue intense
    ---
    """
    summary = fallback_call_llm(prompt)
    assert "PATIENT OVERVIEW" in summary
    assert "Patient de 67 ans" in summary
    assert "KEY FINDINGS" in summary
    assert "RECOMMENDED ACTIONS" in summary

def test_end_to_end_mock_pipeline():
    # Verify the entire pipeline operates with offline fallback
    report_path = root / "data" / "reports" / "report_01.txt"
    report_text = read_report(str(report_path))
    
    # 1. Extractor
    extracted = agent_extractor.run(report_text)
    assert len(extracted) > 0
    assert any(p["parameter"] == "hemoglobine" for p in extracted)
    
    # 2. Interpreter
    annotated = agent_interpreter.run(extracted, gender="male")
    assert len(annotated) == len(extracted)
    assert any(p["parameter"] == "Hémoglobine" and p["status"] == "CRITICAL" for p in annotated)
    
    # 3. Alerter
    alert_report = agent_alerter.run(annotated)
    assert alert_report["critical_count"] > 0
    assert len(alert_report["alerts"]) > 0
    
    # 4. Writer
    summary = agent_writer.run(annotated, alert_report, report_text)
    assert "PATIENT OVERVIEW" in summary
    assert "CRITICAL ALERTS" in summary
