# 🧬 MedAgent

> **Multi-agent clinical report analysis powered by CrewAI and BitNet b1.58**

MedAgent automatically analyzes medical lab reports (PDF or text), classifies every biological parameter against international reference ranges, prioritizes critical alerts, and generates a structured clinical summary — in under 3 seconds.

Built as an academic project for the Applied AI module at ENSIAS, by **Zakariae BELLIL** and **Aymane EL AKKIOUI**.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agents](#agents)
- [LLM & Fallback](#llm--fallback-cascade)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Running Tests](#running-tests)
- [Sample Output](#sample-output)
- [Limitations](#limitations)

---

## Overview

Medical staff in emergency departments manually read dozens of lab reports per shift. MedAgent automates this process with a 4-agent sequential pipeline:

| Step | Agent | Method | Output |
|------|-------|--------|--------|
| 1 | **Extractor** | LLM + PDFReaderTool | JSON array of parameters |
| 2 | **Interpreter** | Deterministic thresholds | Annotated list with NORMAL / ABNORMAL / CRITICAL |
| 3 | **Alerter** | LLM | Prioritized alert list with clinical actions |
| 4 | **Writer** | LLM | Structured medical summary |

**Key design decision:** classification (Agent 2) is fully deterministic — no LLM is involved. This guarantees 100% reproducible and medically accurate classification regardless of model quality.

---

## Architecture

```
Medical Report (PDF / TXT)
         │
         ▼
┌─────────────────────────────────────────────┐
│              CrewAI Crew                     │
│         Process.sequential                   │
│                                              │
│  ┌──────────────┐    ┌───────────────────┐  │
│  │  Agent 1     │    │  PDFReaderTool    │  │
│  │  Extractor   │───▶│  (BaseTool)       │  │
│  └──────┬───────┘    └───────────────────┘  │
│         │                                    │
│  ┌──────▼───────┐    ┌───────────────────┐  │
│  │  Agent 2     │    │  BulkThreshold    │  │
│  │  Interpreter │───▶│  CheckerTool      │  │
│  └──────┬───────┘    └───────────────────┘  │
│         │                                    │
│  ┌──────▼───────┐                           │
│  │  Agent 3     │  (LLM — clinical actions) │
│  │  Alerter     │                           │
│  └──────┬───────┘                           │
│         │                                    │
│  ┌──────▼───────┐                           │
│  │  Agent 4     │  (LLM — summary writing)  │
│  │  Writer      │                           │
│  └──────┬───────┘                           │
└─────────┼───────────────────────────────────┘
          │
          ▼
   MD + HTML + PDF outputs
```

### Communication pattern

Agents communicate via **sequential context passing** — the output of each task is passed as context to the next task in the CrewAI pipeline. No shared state, no blackboard.

---

## Agents

### Agent 1 — Extractor
- **Tool:** `PDFReaderTool` — reads the file and returns raw text
- **LLM task:** extract all biological parameters as a JSON array
- **Output:** `[{"parameter": "hemoglobine", "value": 6.8, "unit": "g/dL", "source_context": "..."}]`
- **Explainability:** each parameter stores its original source line for clinical traceability

### Agent 2 — Interpreter
- **Tool:** `BulkThresholdCheckerTool` — deterministic, no LLM
- **Logic:** compares each value against `config/thresholds.json` (30+ parameters, WHO/ABIM standards)
- **Gender-aware:** separate reference ranges for male / female
- **Output:** annotated list with `status` (NORMAL / ABNORMAL / CRITICAL) and `clinical_risk`

### Agent 3 — Alerter
- **Input:** annotated parameter list from Agent 2
- **LLM task:** for each CRITICAL or ABNORMAL value, generate one concrete clinical action
- **Output:** alert list sorted by urgency (HIGH → MEDIUM), with actions

### Agent 4 — Writer
- **Input:** context from all three previous agents
- **LLM task:** write a structured 4-section clinical summary
- **Output:** PATIENT OVERVIEW / KEY FINDINGS / CRITICAL ALERTS / RECOMMENDED ACTIONS

---

## LLM & Fallback Cascade

MedAgent is designed to run in hospital environments where network connectivity may be limited. The LLM layer tries each option in order:

```
1. BitNet b1.58 (Docker, local)     ← default, CPU-only, no internet
         │ if unavailable
         ▼
2. Google Gemini API                 ← set GEMINI_API_KEY in .env
         │ if unavailable
         ▼
3. Anthropic Claude API             ← set ANTHROPIC_API_KEY in .env
```

A 200ms TCP ping checks server availability before each call to avoid long timeouts. Fallback switching is automatic, transparent, and logged.

---

## Project Structure

```
MedAgent/
│
├── crew.py                      # CrewAI agents, tasks, and Crew assembly
├── main.py                      # CLI entry point
├── app.py                       # Streamlit web interface
│
├── crewai_tools/
│   ├── pdf_tool.py              # PDFReaderTool (BaseTool wrapper)
│   ├── threshold_tool.py        # BulkThresholdCheckerTool (BaseTool wrapper)
│   └── __init__.py
│
├── agents/                      # Legacy standalone agents (kept for reference)
│   ├── agent_extractor.py
│   ├── agent_interpreter.py
│   ├── agent_alerter.py
│   └── agent_writer.py
│
├── tools/
│   ├── pdf_reader.py            # PDF and TXT file reader
│   ├── threshold_checker.py     # Deterministic classification logic
│   └── report_generator.py      # MD + HTML + PDF export
│
├── config/
│   ├── prompts/
│   │   ├── extractor.txt        # Agent 1 prompt template
│   │   ├── alerter.txt          # Agent 3 prompt template
│   │   └── writer.txt           # Agent 4 prompt template
│   ├── thresholds.json          # Medical reference ranges (WHO/ABIM)
│   └── prompt_loader.py
│
├── llm/
│   ├── model.py                 # Fallback cascade LLM caller
│   └── fallback.py              # Offline rule-based fallback engine
│
├── data/reports/                # Input reports (.pdf or .txt)
├── output/summaries/            # Generated MD, HTML, PDF outputs
├── test/                        # pytest test suite
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env
```

---

## Quick Start

### Option A — Docker (recommended)

Starts BitNet server + Streamlit UI automatically:

```bash
git clone https://github.com/AymaneAki/MedAgent.git
cd MedAgent
cp .env.example .env       # configure API keys if needed
docker compose up --build
```

Open **http://localhost:8501** in your browser.

> **Note:** BitNet takes ~60 seconds to load on first start. The UI waits automatically.

### Option B — Local Python

```bash
git clone https://github.com/AymaneAki/MedAgent.git
cd MedAgent
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

You'll need either a running BitNet server or a cloud API key configured in `.env`.

---

## Usage

### Web Interface

Upload a `.pdf` or `.txt` report via the Streamlit UI. The pipeline runs automatically and displays:
- classified parameters table with color-coded status badges
- critical alerts section
- structured clinical summary
- downloadable MD / HTML / PDF outputs

### CLI — single report

```bash
python main.py --file data/reports/report_01.txt
```

With gender override for accurate reference ranges:

```bash
python main.py --file data/reports/report_02.txt --gender female
```

### CLI — batch processing

```bash
python main.py --dir data/reports/ --output-dir output/summaries/
```

### Docker CLI

```bash
docker compose run --rm medagents-cli --file data/reports/report_01.txt
docker compose run --rm medagents-cli --dir data/reports/
```

---

## Configuration

Copy `.env.example` to `.env` and set the relevant variables:

```env
# Local BitNet server (Docker) — default, no key needed
BITNET_BASE_URL=http://bitnet-server:11434
BITNET_MODEL=bitnet-b1.58-2b-4t

# Fallback: Google Gemini
# GEMINI_API_KEY=your_key_here

# Fallback: Anthropic Claude
# ANTHROPIC_API_KEY=your_key_here

LOG_LEVEL=INFO
```

---

## Running Tests

```bash
pytest test/test_medagent.py -v
```

Expected output:

```
test/test_medagent.py::test_threshold_checker     PASSED
test/test_medagent.py::test_pdf_reader            PASSED
test/test_medagent.py::test_fallback_extractor    PASSED
test/test_medagent.py::test_fallback_alerter      PASSED
test/test_medagent.py::test_fallback_writer       PASSED
test/test_medagent.py::test_pipeline_end_to_end   PASSED
test/test_medagent.py::test_ocr_stress            PASSED

9 passed in 3.12s
```

---

## Sample Output

Input: `report_02_small.txt` (female patient, 34 years old)

```
PATIENT OVERVIEW
Patient de 34 ans, Féminin.
Motif : Douleurs abdominales, nausées, vomissements.
Antécédents : Diabète type 1, Lupus, Anémie ferriprive.

KEY FINDINGS
• Plaquettes: 44.0 G/L (normal: 150–400)  → CRITIQUE 🔴
• Lipase: 640.0 U/L (normal: 0–160)        → CRITIQUE 🔴
• Fibrinogène: 0.9 g/L (normal: 2.0–4.0)  → CRITIQUE 🔴
• TSH: 0.08 mUI/L (normal: 0.4–4.0)       → CRITIQUE 🔴
• Hémoglobine: 8.4 g/dL (normal: 12–16)   → ANORMAL 🟡
• Leucocytes: 18.6 G/L (normal: 4–10)     → ANORMAL 🟡

CRITICAL ALERTS 🔴
• Plaquettes 44 G/L — Thrombopénie sévère, risque hémorragique spontané
• Lipase 640 U/L — Pancréatite aiguë sévère
• Fibrinogène 0.9 g/L — CIVD ou insuffisance hépatique sévère
• TSH 0.08 mUI/L — Crise thyrotoxique possible

RECOMMENDED ACTIONS
1. [HIGH] Transfusion plaquettaire en urgence
2. [HIGH] Mise à jeun + hydratation IV + échographie abdominale urgente
3. [HIGH] Plasma frais congelé (PFC) en urgence, bilan CIVD
4. [HIGH] Antithyroïdiens + bêtabloquants + avis endocrinologique
```

---

## Limitations

- **Small LLM quality:** BitNet b1.58 2B is a very lightweight model. Clinical action recommendations may lack precision for rare or complex cases. The fallback cascade to Gemini or Claude produces better results.
- **Structured reports only:** the extractor is optimized for formatted lab reports. Unstructured clinical notes or handwritten scans are not supported.
- **No medical certification:** MedAgent is an academic prototype. It must not be used for real clinical decisions without validation by qualified medical professionals.
- **Reference ranges:** thresholds are based on WHO/ABIM adult standards. Pediatric, pregnancy, or population-specific ranges are not currently included.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent orchestration | CrewAI |
| LLM (local) | BitNet b1.58 2B4T |
| LLM (fallback) | Gemini API / Claude API |
| Web interface | Streamlit |
| PDF parsing | pypdf |
| Report export | FPDF2 |
| Tests | pytest |
| Containerization | Docker Compose |

---

## Authors

**Zakariae BELLIL** · **Aymane EL AKKIOUI**
ENSIAS — Module IA & Applications — 2026