# main.py
#
# Entry point for the MedAgent CrewAI pipeline.
# Supports single file and batch directory processing.
#
# Usage:
#   python main.py --file data/reports/report_01.txt
#   python main.py --dir  data/reports/
#   python main.py --file data/reports/report_01.txt --gender male

import os
import sys
import re
import logging
import argparse
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.append(str(root))

from crew                   import build_crew
from tools.pdf_reader       import read_report
from tools.report_generator import generate_reports


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO"):
    os.makedirs(root / "logs", exist_ok=True)
    logging.basicConfig(
        level   = getattr(logging, level.upper(), logging.INFO),
        format  = "%(asctime)s [%(levelname)s] %(message)s",
        handlers = [
            logging.FileHandler(root / "logs" / "medagent.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ── Demographics parser ───────────────────────────────────────────────────────

def parse_demographics(report_text: str) -> dict:
    age_m    = re.search(r"(?:Âge|Age)\s*:\s*([^\n]+)",  report_text, re.IGNORECASE)
    gender_m = re.search(r"Sexe\s*:\s*([^\n]+)",          report_text, re.IGNORECASE)
    reason_m = re.search(r"(?:Motif|Admission)\s*:\s*([^\n]+)", report_text, re.IGNORECASE)

    gender_raw = gender_m.group(1).lower() if gender_m else ""
    if "fem" in gender_raw or "fém" in gender_raw:
        gender_key   = "female"
        gender_label = "Féminin"
    elif "mas" in gender_raw or "hom" in gender_raw:
        gender_key   = "male"
        gender_label = "Masculin"
    else:
        gender_key   = "default"
        gender_label = "Non spécifié"

    return {
        "age":        age_m.group(1).strip()    if age_m    else "Non fourni",
        "gender":     gender_label,
        "gender_key": gender_key,
        "reason":     reason_m.group(1).strip() if reason_m else "Non fourni",
        "history":    "Non fourni",
    }


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(file_path: Path,
                 gender_override: str = None,
                 output_dir: Path     = None) -> bool:

    output_dir = output_dir or (root / "output" / "summaries")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Processing: {file_path.name}")
    print(f"{'='*60}")

    try:
        # ── Parse demographics for report generation ──────────────────────────
        report_text  = read_report(str(file_path))
        demographics = parse_demographics(report_text)
        gender       = gender_override or demographics["gender_key"]

        print(f"  Patient: {demographics['age']}, "
              f"{demographics['gender']}, {demographics['reason'][:50]}")

        # ── Run CrewAI pipeline ───────────────────────────────────────────────
        print("\n  🚀 Starting CrewAI pipeline...\n")
        crew   = build_crew(str(file_path), gender)
        result = crew.kickoff()

        # crew.kickoff() returns the final task output (writer summary)
        summary = str(result)

        print(f"\n{'='*60}")
        print("  FINAL SUMMARY")
        print(f"{'='*60}")
        print(summary)

        # ── Parse annotated params from crew tasks for report generation ──────
        # Access task outputs stored in crew.tasks
        tasks          = crew.tasks
        annotated_raw  = tasks[1].output.raw if len(tasks) > 1 else "[]"
        alert_raw      = tasks[2].output.raw if len(tasks) > 2 else ""

        # Parse annotated params — try JSON, fallback to empty list
        try:
            import json, re as _re
            match = _re.search(r"\[.*\]", annotated_raw, _re.DOTALL)
            annotated_params = json.loads(match.group()) if match else []
        except Exception:
            annotated_params = []

        # Build minimal alert_report for report generator
        critical = [p for p in annotated_params if p.get("status") == "CRITICAL"]
        abnormal = [p for p in annotated_params if p.get("status") == "ABNORMAL"]
        alert_report = {
            "critical_count": len(critical),
            "abnormal_count": len(abnormal),
            "alerts": [
                {**p, "urgency": "HIGH" if p["status"] == "CRITICAL" else "MEDIUM", "action": ""}
                for p in critical + abnormal
            ]
        }

        # ── Generate MD + HTML + PDF outputs ─────────────────────────────────
        print("\n  💾 Generating output files (MD, HTML, PDF)...")
        output_base = str(output_dir / (file_path.stem + "_summary"))
        generate_reports(
            patient_info    = demographics,
            annotated_params= annotated_params,
            alert_report    = alert_report,
            summary_text    = summary,
            output_path_base= output_base,
        )
        print(f"  ✅ Saved to: {output_dir}")
        print(f"     • {file_path.stem}_summary.md")
        print(f"     • {file_path.stem}_summary.html")
        print(f"     • {file_path.stem}_summary.pdf")
        return True

    except Exception as e:
        logging.error(f"Pipeline failed for {file_path.name}: {e}", exc_info=True)
        print(f"\n  ❌ Error: {e}")
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MedAgent — Multi-agent clinical report analysis powered by CrewAI"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", "-f", type=str,
                       help="Path to a single .txt or .pdf report")
    group.add_argument("--dir",  "-d", type=str,
                       help="Directory containing reports to process in batch")

    parser.add_argument("--gender", "-g",
                        choices=["male", "female", "default"], default=None,
                        help="Override gender for reference ranges")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Output directory for generated reports")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()
    setup_logging(args.log_level)

    out = Path(args.output_dir) if args.output_dir else root / "output" / "summaries"

    if args.file:
        fp = Path(args.file)
        if not fp.exists():
            print(f"❌ File not found: {fp}")
            sys.exit(1)
        success = run_pipeline(fp, args.gender, out)
        sys.exit(0 if success else 1)

    elif args.dir:
        dp = Path(args.dir)
        if not dp.exists():
            print(f"❌ Directory not found: {dp}")
            sys.exit(1)
        files = list(dp.glob("*.txt")) + list(dp.glob("*.pdf"))
        if not files:
            print(f"⚠️  No .txt or .pdf files found in {dp}")
            sys.exit(0)

        print(f"📂 Found {len(files)} report(s) — starting batch processing")
        ok = sum(1 for f in files if run_pipeline(f, args.gender, out))
        print(f"\n✅ Done: {ok}/{len(files)} reports processed successfully")
        sys.exit(0 if ok == len(files) else 1)


if __name__ == "__main__":
    main()