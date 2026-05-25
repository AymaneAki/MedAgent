# main.py

import os
import sys
import re
import argparse
import logging
from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parent
sys.path.append(str(root))

from tools.pdf_reader import read_report
from tools.report_generator import generate_reports
from agents import (
    agent_extractor,
    agent_interpreter,
    agent_alerter,
    agent_writer
)

# Colors for terminal output
class TerminalColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def safe_print(text=""):
    """
    Safely prints text on Windows console by converting emojis and box-drawing
    characters to ASCII if the console character map does not support them.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        cleaned = str(text)
        replacements = {
            "📄": "[DOC]",
            "🔍": "[FIND]",
            "🧪": "[TEST]",
            "🚨": "[ALERT]",
            "📋": "[WRITE]",
            "💾": "[SAVE]",
            "🔴": "[CRITICAL]",
            "🟡": "[ABNORMAL]",
            "🟢": "[NORMAL]",
            "✓": "[OK]",
            "❌": "[ERROR]",
            "✨": "[SUCCESS]",
            "📂": "[DIR]",
            "📊": "[STATS]",
            "┌": "+",
            "─": "-",
            "┐": "+",
            "│": "|",
            "└": "+",
            "┘": "+",
            "→": "->",
            "•": "-",
            "Â": "A",
            "â": "a",
            "é": "e",
            "è": "e",
            "à": "a",
            "ù": "u"
        }
        for k, v in replacements.items():
            cleaned = cleaned.replace(k, v)
        try:
            print(cleaned.encode(sys.stdout.encoding, errors='ignore').decode(sys.stdout.encoding))
        except Exception:
            # Absolute fallback
            print(cleaned.encode('ascii', errors='ignore').decode('ascii'))

def setup_logging(log_level_str="INFO"):
    log_dir = root / "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "medagent.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Silence third-party logs
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

def parse_demographics(report_text: str) -> dict:
    """Parses patient demographics using regex from report text."""
    age_match = re.search(r"(?:Âge|Age)\s*:\s*([^\n]+)", report_text, re.IGNORECASE)
    gender_match = re.search(r"Sexe\s*:\s*([^\n]+)", report_text, re.IGNORECASE)
    reason_match = re.search(r"Motif\s*:\s*([^\n]+)", report_text, re.IGNORECASE)
    
    gender_str = "default"
    if gender_match:
        g = gender_match.group(1).lower()
        if "fem" in g or "fém" in g:
            gender_str = "female"
        elif "mas" in g or "hom" in g:
            gender_str = "male"

    return {
        "age": age_match.group(1).strip() if age_match else "Non fourni dans le rapport",
        "gender": "Féminin" if gender_str == "female" else "Masculin" if gender_str == "male" else "Non spécifié",
        "gender_key": gender_str,
        "reason": reason_match.group(1).strip() if reason_match else "Non fourni dans le rapport",
        "history": "Non fourni dans le rapport"
    }

def run_pipeline(file_path: Path, gender_override: str = None, output_dir: Path = None) -> bool:
    """Runs the complete 4-agent clinical analysis pipeline for a single file."""
    if not output_dir:
        output_dir = root / "output" / "summaries"
    os.makedirs(output_dir, exist_ok=True)

    safe_print(f"\n{TerminalColors.BOLD}{TerminalColors.BLUE}+--------------------------------------------------------+{TerminalColors.ENDC}")
    safe_print(f"{TerminalColors.BOLD}{TerminalColors.BLUE}|  Traitement de : {file_path.name:<37} |{TerminalColors.ENDC}")
    safe_print(f"{TerminalColors.BOLD}{TerminalColors.BLUE}+--------------------------------------------------------+{TerminalColors.ENDC}")

    try:
        # Step 1: Read Report
        safe_print("📄 Lecture du rapport...")
        report_text = read_report(str(file_path))
        safe_print(f"   → {TerminalColors.GREEN}Rapport lu successfully ({len(report_text)} caractères).{TerminalColors.ENDC}")
        
        # Parse demographics
        demographics = parse_demographics(report_text)
        gender = gender_override if gender_override else demographics["gender_key"]
        safe_print(f"   → Profil détecté : Âge: {demographics['age']}, Genre: {demographics['gender']}, Motif: {demographics['reason'][:40]}...")

        # Step 2: Extractor Agent
        safe_print("🔍 Agent 1 — Extraction des constantes biologiques...")
        extracted = agent_extractor.run(report_text)
        safe_print(f"   → {TerminalColors.GREEN}{len(extracted)} paramètres biologiques extraits.{TerminalColors.ENDC}")
        for p in extracted[:5]:
            safe_print(f"      • {p['parameter']:<22} : {p['value']} {p['unit']}")
        if len(extracted) > 5:
            safe_print(f"      • ... et {len(extracted) - 5} autres.")

        # Step 3: Interpreter Agent
        safe_print("🧪 Agent 2 — Interpretation biologique...")
        annotated = agent_interpreter.run(extracted, gender=gender)
        critical_count = sum(1 for p in annotated if p["status"] == "CRITICAL")
        abnormal_count = sum(1 for p in annotated if p["status"] == "ABNORMAL")
        safe_print(f"   → {TerminalColors.GREEN}Interprétation complétée.{TerminalColors.ENDC} ({TerminalColors.FAIL}{critical_count} Critiques{TerminalColors.ENDC}, {TerminalColors.WARNING}{abnormal_count} Anormaux{TerminalColors.ENDC})")
        for p in annotated:
            if p["status"] == "CRITICAL":
                safe_print(f"      🔴 {TerminalColors.FAIL}[CRITIQUE]{TerminalColors.ENDC} {p['parameter']:<20} : {p['value']} {p['unit']} (Norme: {p['normal_range']})")
            elif p["status"] == "ABNORMAL":
                safe_print(f"      🟡 {TerminalColors.WARNING}[ANORMAL]{TerminalColors.ENDC}  {p['parameter']:<20} : {p['value']} {p['unit']} (Norme: {p['normal_range']})")

        # Step 4: Alerter Agent
        safe_print("🚨 Agent 3 — Évaluation des risques cliniques...")
        alert_report = agent_alerter.run(annotated)
        safe_print(f"   → {TerminalColors.GREEN}Rapport d'alertes généré avec {len(alert_report['alerts'])} actions requises.{TerminalColors.ENDC}")

        # Step 5: Writer Agent
        safe_print("📋 Agent 4 — Rédaction de la synthèse clinique...")
        summary = agent_writer.run(annotated, alert_report, report_text)
        safe_print(f"   → {TerminalColors.GREEN}Synthèse rédigée successfully.{TerminalColors.ENDC}")

        # Step 6: Generate Outputs
        safe_print("💾 Génération des livrables professionnels (MD, HTML, PDF)...")
        file_base_name = file_path.stem + "_summary"
        output_path_base = str(output_dir / file_base_name)
        
        generate_reports(
            patient_info=demographics,
            annotated_params=annotated,
            alert_report=alert_report,
            summary_text=summary,
            output_path_base=output_path_base
        )
        
        safe_print(f"   → {TerminalColors.BOLD}{TerminalColors.GREEN}Livrables enregistrés dans : {output_dir}{TerminalColors.ENDC}")
        safe_print(f"      • [PDF]  {file_base_name}.pdf")
        safe_print(f"      • [HTML] {file_base_name}.html")
        safe_print(f"      • [MD]   {file_base_name}.md")
        return True

    except Exception as e:
        safe_print(f"   ❌ {TerminalColors.FAIL}Erreur lors du traitement : {e}{TerminalColors.ENDC}")
        logging.error(f"Error processing {file_path.name}: {e}", exc_info=True)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="MedAgent — Plateforme d'analyse et d'alertes biologiques multi-agent."
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file", "-f",
        type=str,
        help="Chemin vers un rapport médical au format .txt ou .pdf"
    )
    group.add_argument(
        "--dir", "-d",
        type=str,
        help="Dossier contenant des rapports médicaux à traiter en lot"
    )
    
    parser.add_argument(
        "--gender", "-g",
        choices=["male", "female", "default"],
        default=None,
        help="Forcer le genre pour les seuils de référence (par défaut, extrait automatiquement)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Dossier de sortie pour les rapports générés"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Niveau de journalisation"
    )
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    output_path = Path(args.output_dir) if args.output_dir else root / "output" / "summaries"
    
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            safe_print(f"{TerminalColors.FAIL}Erreur : Le fichier {file_path} n'existe pas.{TerminalColors.ENDC}")
            sys.exit(1)
        success = run_pipeline(file_path, args.gender, output_path)
        sys.exit(0 if success else 1)
        
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.exists() or not dir_path.is_dir():
            safe_print(f"{TerminalColors.FAIL}Erreur : Le dossier {dir_path} n'existe pas.{TerminalColors.ENDC}")
            sys.exit(1)
            
        safe_print(f"📂 Recherche de rapports dans le dossier : {dir_path}")
        files = []
        for ext in ["*.txt", "*.pdf"]:
            files.extend(list(dir_path.glob(ext)))
            
        if not files:
            safe_print(f"{TerminalColors.WARNING}Aucun fichier .txt ou .pdf trouvé dans {dir_path}.{TerminalColors.ENDC}")
            sys.exit(0)
            
        safe_print(f"📊 {len(files)} rapports trouvés. Début du traitement par lot...")
        success_count = 0
        for f in files:
            if run_pipeline(f, args.gender, output_path):
                success_count += 1
                
        safe_print(f"\n✨ Traitement terminé : {success_count}/{len(files)} fichiers analysés avec succès.")
        sys.exit(0)

if __name__ == "__main__":
    main()

