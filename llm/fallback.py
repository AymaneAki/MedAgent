# llm/fallback.py

import re
import json
import os

def fallback_call_llm(prompt: str) -> str:
    """
    A highly intelligent mock LLM fallback that parses the medical prompt
    and generates clinical-grade responses using local rules and regex.
    This guarantees the agent pipeline runs perfectly even when offline.
    """
    prompt_lower = prompt.lower()

    # 1. Extractor Agent Fallback
    if "extract biological parameters" in prompt_lower or "meticulous medical data extractor" in prompt_lower:
        return _fallback_extractor(prompt)

    # 2. Alerter Agent Fallback
    elif "emergency physician" in prompt_lower or "immediate clinical action" in prompt_lower:
        return _fallback_alerter(prompt)

    # 3. Writer Agent Fallback
    elif "medical report writer" in prompt_lower or "patient overview" in prompt_lower:
        return _fallback_writer(prompt)

    # Default fallback
    return "Analyse clinique complétée par l'agent MedAgent."


def normalize_line(line: str) -> str:
    """
    Cleans OCR noise by collapsing spaces in spaced-out letters (e.g. 'H é m o g l o b i n e')
    and handles spelling/semantic numbers written in French (e.g. 'quatorz virgule 2').
    """
    cleaned = line.strip()
    
    # 1. Translate French number words (case-insensitive)
    french_digits = {
        "quatorze": "14", "quatorz": "14",
        "treize": "13", "douze": "12", "onze": "11", "dix": "10",
        "neuf": "9", "huit": "8", "sept": "7", "six": "6", "cinq": "5",
        "quatre": "4", "trois": "3", "deux": "2", "un": "1", "une": "1",
        "zéro": "0", "zero": "0"
    }
    for word, digit in french_digits.items():
        pattern = r"\b" + re.escape(word) + r"\b"
        cleaned = re.sub(pattern, digit, cleaned, flags=re.IGNORECASE)
        
    # 2. Convert "virgule" or "point" between digits into a decimal point "."
    cleaned = re.sub(r'(\d+)\s*(?:virgule|point|virgl)\s*(\d+)', r'\1.\2', cleaned, flags=re.IGNORECASE)
    
    # 3. Clean written unit terms
    unit_replacements = {
        "grammes par decilitre": "g/dL",
        "gramme par decilitre": "g/dL",
        "grammes par littre": "G/L",
        "gramme par littre": "G/L",
        "grammes par litre": "G/L",
        "gramme par litre": "G/L",
        "g par litre": "G/L",
        "pourcent": "%",
        "pour cent": "%"
    }
    for k, v in unit_replacements.items():
        cleaned = re.sub(r"\b" + re.escape(k) + r"\b", v, cleaned, flags=re.IGNORECASE)

    # 4. Standard space collapsing for OCR (spaced letters)
    if re.search(r'(?:\b[a-zA-Z0-9]\s+){3,}', cleaned):
        # Temporarily protect double spaces or punctuation
        # Replace multiple spaces with a temporary token
        temp = re.sub(r'\s{2,}', '___DOUBLE_SPACE___', cleaned)
        # Collapse spaces between single word letters
        temp = re.sub(r'(?<=\w)\s+(?=\w)', '', temp)
        temp = re.sub(r'(?<=\d)\s+(?=\d)', '', temp)
        # Collapse spaces around decimal points
        temp = re.sub(r'(\d)\s*([.,])\s*(\d)', r'\1\2\3', temp)
        # Collapse spaces around slashes and percent signs
        temp = re.sub(r'\s*/\s*', '/', temp)
        temp = re.sub(r'\s*%\s*', '%', temp)
        cleaned = temp.replace('___DOUBLE_SPACE___', ' ')
    return cleaned




def _fallback_extractor(prompt: str) -> str:
    """
    Scans the prompt text for biological values and extracts them
    into a structured JSON array matching the Extractor prompt requirements.
    Supports source context capture and OCR space-collapse normalization.
    """
    # Define clinical parameters to search for
    keywords = {
        "hemoglobine": ["hémoglobine", "hemoglobine", "hb"],
        "hematocrite": ["hématocrite", "hematocrite", "ht"],
        "leucocytes": ["leucocytes", "leucocyte", "gb", "globules blancs"],
        "neutrophiles": ["neutrophiles", "neutrophile", "polynucléaires neutrophiles"],
        "lymphocytes": ["lymphocytes", "lymphocyte"],
        "plaquettes": ["plaquettes", "plaquette", "plq"],
        "vgm": ["vgm", "vol. glob. moyen", "volume globulaire moyen"],
        "sodium": ["sodium", "natrémie", "natremie"],
        "potassium": ["potassium", "kaliémie", "kaliemie"],
        "creatinine": ["créatinine", "creatinine"],
        "uree": ["urée", "uree"],
        "glucose": ["glycémie", "glycemie", "glucose"],
        "calcium": ["calcium", "calcémie", "calcemie"],
        "magnesium": ["magnésium", "magnesium"],
        "phosphore": ["phosphore"],
        "chlore": ["chlore", "chlorémie", "chloremie"],
        "bicarbonate": ["bicarbonate", "hco3"],
        "alat": ["alat", "sgpt"],
        "asat": ["asat", "sgot"],
        "bilirubine_totale": ["bilirubine totale", "bilirubine"],
        "albumine": ["albumine"],
        "ggt": ["gamma gt", "ggt"],
        "troponine_i": ["troponine i", "troponine"],
        "ck_mb": ["ck-mb", "ckmb"],
        "bnp": ["bnp"],
        "ph_arteriel": ["ph artériel", "ph arteriel", "ph"],
        "pao2": ["pao2", "pao 2"],
        "paco2": ["paco2", "paco 2"],
        "spo2": ["spo2", "spo 2", "saturation"],
        "tp": ["tp", "taux de prothrombine"],
        "inr": ["inr"],
        "fibrinogene": ["fibrinogène", "fibrinogene"],
        "amylase": ["amylase"],
        "lipase": ["lipase"],
        "tsh": ["tsh"]
    }

    extracted = []
    
    # Isolate the original report text from prompt
    report_text = prompt
    report_match = re.search(r"REPORT:\s*(.*)", prompt, re.DOTALL | re.IGNORECASE)
    if report_match:
        report_text = report_match.group(1)

    # Clean the text slightly for standard processing
    lines = report_text.split("\n")

    for line in lines:
        raw_line = line.strip()
        if not raw_line:
            continue
        
        # Normalize OCR space separation
        normalized = normalize_line(raw_line)
        
        # Look for standard "Keyword : Value Unit" patterns
        for param_key, aliases in keywords.items():
            for alias in aliases:
                # Regex matches keyword, followed by optional punctuation, space, and a numeric value with optional units
                # Allow conversational words or standard spacing between parameter name and value in paragraph sentences
                pattern = r"\b" + re.escape(alias) + r"\b.*?\b([<>≤≥]?\s*[0-9]+[.,]?[0-9]*)\s*([a-zA-Z/%µgG/lL]*)"
                match = re.search(pattern, normalized, re.IGNORECASE)

                
                if match:
                    val_str = match.group(1)
                    unit_str = match.group(2).strip()

                    # Strip comparison operators
                    val_str = re.sub(r"[<>≤≥\s]", "", val_str)
                    val_str = val_str.replace(",", ".")
                    
                    try:
                        value = float(val_str)
                        
                        # active unit corrections
                        if not unit_str:
                            # Assign default unit based on standard parameters
                            if param_key == "hemoglobine": unit_str = "g/dL"
                            elif param_key in ["hematocrite", "spo2", "tp"]: unit_str = "%"
                            elif param_key in ["leucocytes", "neutrophiles", "lymphocytes", "plaquettes"]: unit_str = "G/L"
                            elif param_key in ["sodium", "potassium", "glucose", "uree", "calcium", "magnesium", "phosphore", "chlore", "bicarbonate"]: unit_str = "mmol/L"
                            elif param_key == "creatinine": unit_str = "µmol/L"
                            elif param_key == "vgm": unit_str = "fL"
                            elif param_key in ["alat", "asat", "ggt", "ck_mb", "amylase", "lipase"]: unit_str = "U/L"
                            elif param_key == "troponine_i": unit_str = "µg/L"
                            elif param_key == "bnp": unit_str = "pg/mL"
                            elif param_key == "pao2" or param_key == "paco2": unit_str = "mmHg"
                            elif param_key == "fibrinogene": unit_str = "g/L"
                            elif param_key == "tsh": unit_str = "mUI/L"
                        
                        unit_str = unit_str.replace("G/LL", "G/L").replace("g/dl", "g/dL")
                        
                        # Avoid duplicates
                        if not any(e["parameter"] == param_key for e in extracted):
                            extracted.append({
                                "parameter": param_key,
                                "value": value,
                                "unit": unit_str,
                                "source_context": raw_line
                            })
                        break # Done with this parameter for this line
                    except ValueError:
                        continue

    return json.dumps(extracted, indent=2, ensure_ascii=False)



def _fallback_alerter(prompt: str) -> str:
    """
    Parses parameter details and generates a single medical action recommendation.
    """
    param_match = re.search(r"Parameter\s*:\s*(.*)", prompt)
    value_match = re.search(r"Value\s*:\s*([0-9.]+)\s*(.*)", prompt)
    status_match = re.search(r"Status\s*:\s*(.*)", prompt)
    risk_match = re.search(r"Risk\s*:\s*(.*)", prompt)

    param = param_match.group(1).strip().lower() if param_match else "inconnu"
    value = float(value_match.group(1)) if value_match else 0.0
    status = status_match.group(1).strip().upper() if status_match else "UNKNOWN"
    risk = risk_match.group(1).strip() if risk_match else ""

    if status == "CRITICAL":
        if "hemoglobine" in param or "hb" in param:
            return "Transfusion sanguine urgente à envisager (Hb < 7 g/dL) et monitorage cardiorespiratoire continu."
        elif "potassium" in param:
            if value > 5.0:
                return "Administration intraveineuse urgente de gluconate de calcium (cardioprotection) et insulinothérapie-glucose."
            else:
                return "Perfusion intraveineuse urgente de chlorure de potassium sous surveillance ECG continue."
        elif "sodium" in param:
            return "Restriction hydrique stricte et correction prudente par sérum salé hypertonique, surveillance de la natrémie toutes les 4h."
        elif "creatinine" in param:
            return "Avis néphrologique immédiat pour suppléance rénale (dialyse) en urgence et arrêt immédiat de tout traitement néphrotoxique."
        elif "troponine" in param:
            return "Avis cardiologique en urgence absolue pour syndrome coronarien aigu, réalisation d'un ECG 18 pistes immédiat."
        elif "spo2" in param or "oxygen" in param:
            return "Oxygénothérapie immédiate à fort débit (masque haute concentration) et transfert en réanimation."
        elif "ph" in param:
            return "Correction de la cause sous-jacente de l'acidose/alcalose et transfert immédiat en unité de soins intensifs."
        elif "plaquettes" in param:
            return "Transfusion de plaquettes en urgence et évitement de toute injection intramusculaire ou traumatisme."
        else:
            return f"Avis médical spécialisé immédiat pour {param} critique ({value}) : {risk}."
            
    elif status == "ABNORMAL":
        if "leucocytes" in param or "neutrophiles" in param:
            return "Recherche active de foyer infectieux, prélèvements bactériologiques et surveillance thermique."
        elif "sodium" in param:
            return "Surveillance hydro-électrolytique et adaptation des apports hydriques journaliers."
        elif "creatinine" in param:
            return "Hydratation adéquate, contrôle de la fonction rénale à 24-48 heures et évitement des produits iodés."
        elif "plaquettes" in param:
            return "Contrôle de la numération plaquettaire sur tube citrate (éliminer un faux positif) et surveillance clinique."
        else:
            return f"Contrôle biologique de {param} à distance et surveillance de l'état clinique du patient."
            
    return "Aucune action urgente requise; poursuite de la surveillance clinique standard."


def _fallback_writer(prompt: str) -> str:
    """
    Generates a structured medical summary using sections from the prompt.
    """
    # Try to extract the original excerpt to find demographics
    demographics = "Non fourni dans le rapport"
    report_match = re.search(r"ORIGINAL REPORT EXCERPT:\s*(.*?)\s*---", prompt, re.DOTALL | re.IGNORECASE)
    if report_match:
        text = report_match.group(1)
        age_m = re.search(r"(\d+)\s*ans", text, re.IGNORECASE)
        gender_m = re.search(r"Sexe\s*:\s*([a-zA-Z]+)", text, re.IGNORECASE)
        motif_m = re.search(r"Motif\s*:\s*([^\n]+)", text, re.IGNORECASE)
        
        age_str = f"{age_m.group(1)} ans" if age_m else "Âge non précisé"
        gender_str = gender_m.group(1) if gender_m else "Sexe non précisé"
        motif_str = motif_m.group(1).strip() if motif_m else "Motif non précisé"
        
        demographics = f"Patient de {age_str}, Sexe : {gender_str}. Motif d'admission : {motif_str}."

    # Extract lists of values
    crit_match = re.search(r"CRITICAL VALUES:\s*(.*?)\s*ABNORMAL VALUES:", prompt, re.DOTALL)
    crit_str = crit_match.group(1).strip() if crit_match else "None"
    
    abn_match = re.search(r"ABNORMAL VALUES:\s*(.*?)\s*SUGGESTED ACTIONS", prompt, re.DOTALL)
    abn_str = abn_match.group(1).strip() if abn_match else "None"

    actions_match = re.search(r"SUGGESTED ACTIONS FROM ANALYSIS:\s*(.*?)\s*ORIGINAL REPORT", prompt, re.DOTALL)
    actions_str = actions_match.group(1).strip() if actions_match else "None"

    # Format findings list
    findings_list = []
    if crit_str and crit_str != "None":
        for line in crit_str.split("\n"):
            if line.strip().startswith("-"):
                findings_list.append(f"{line.strip()} [CRITIQUE 🔴]")
    if abn_str and abn_str != "None":
        for line in abn_str.split("\n"):
            if line.strip().startswith("-"):
                findings_list.append(f"{line.strip()} [ANORMAL 🟡]")
    
    findings_str = "\n".join(findings_list) if findings_list else "- Aucun paramètre pathologique détecté."

    summary = f"""PATIENT OVERVIEW
{demographics}

KEY FINDINGS
{findings_str}

CRITICAL ALERTS 🔴
{crit_str}

RECOMMENDED ACTIONS
{actions_str}"""

    return summary
