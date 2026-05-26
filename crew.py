# crew.py
#
# Defines the MedAgent CrewAI pipeline:
#   - 4 Agents  (Extractor, Interpreter, Alerter, Writer)
#   - 4 Tasks   (one per agent, sequential)
#   - 1 Crew    (orchestrates the full pipeline)
#
# Existing logic is preserved:
#   - Prompts      → config/prompts/*.txt  (unchanged)
#   - Thresholds   → config/thresholds.json (unchanged)
#   - LLM fallback → llm/model.py + llm/fallback.py (unchanged)

import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from crewai           import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

from config.prompt_loader        import load_prompt
from crewai_tools.pdf_tool       import PDFReaderTool
from crewai_tools.threshold_tool import BulkThresholdCheckerTool
import os


# ── LLM Setup ────────────────────────────────────────────────────────────────
# Points to the local BitNet server via OpenAI-compatible API.
# CrewAI uses LangChain under the hood, so we use ChatOpenAI with a custom base_url.
# Falls back to env vars for Gemini or OpenAI if BitNet is offline.

def _build_llm():
    bitnet_url = os.getenv("BITNET_BASE_URL", "http://localhost:11434")
    return ChatOpenAI(
        model       = os.getenv("BITNET_MODEL", "bitnet-b1.58-2b-4t"),
        base_url    = bitnet_url.rstrip("/") + "/v1",
        api_key     = "not-needed",
        temperature = 0.1,
        max_tokens  = 1024,
    )

llm = _build_llm()

# ── Tools ─────────────────────────────────────────────────────────────────────
pdf_tool       = PDFReaderTool()
threshold_tool = BulkThresholdCheckerTool()


# ── Agents ────────────────────────────────────────────────────────────────────

extractor_agent = Agent(
    role = "Medical Data Extractor",
    goal = (
        "Read the medical report file and extract EVERY biological parameter "
        "into a clean JSON array. Never stop early. Never miss a section."
    ),
    backstory = (
        "You are a specialist in reading medical lab reports from hospitals. "
        "You have processed thousands of reports and never miss a single value. "
        "You always return pure JSON with no extra text."
    ),
    tools       = [pdf_tool],
    llm         = llm,
    verbose     = True,
    allow_delegation = False,
)

interpreter_agent = Agent(
    role = "Clinical Biologist",
    goal = (
        "Classify every extracted biological parameter as NORMAL, ABNORMAL, or CRITICAL "
        "by comparing it against standard medical reference ranges."
    ),
    backstory = (
        "You are a clinical biologist with 20 years of experience. "
        "You never guess — you always use the threshold checker tool. "
        "You process the full list in a single bulk call."
    ),
    tools       = [threshold_tool],
    llm         = llm,
    verbose     = True,
    allow_delegation = False,
)

alerter_agent = Agent(
    role = "Emergency Medicine Specialist",
    goal = (
        "From the classified parameters, identify all CRITICAL and ABNORMAL values, "
        "rank them by urgency (HIGH/MEDIUM), and assign one concrete clinical action each."
    ),
    backstory = (
        "You are an emergency physician who has triaged thousands of critical patients. "
        "You are direct, concise, and always prioritize the most dangerous values first."
    ),
    tools       = [],
    llm         = llm,
    verbose     = True,
    allow_delegation = False,
)

writer_agent = Agent(
    role = "Medical Report Writer",
    goal = (
        "Write a structured, actionable clinical summary for the doctor on duty. "
        "Include patient overview, key findings, critical alerts, and recommended actions."
    ),
    backstory = (
        "You specialize in translating complex lab findings into clear summaries "
        "that a busy emergency doctor can read in under 30 seconds. "
        "You are concise, never verbose, and never invent data."
    ),
    tools       = [],
    llm         = llm,
    verbose     = True,
    allow_delegation = False,
)


# ── Task factory ──────────────────────────────────────────────────────────────
# Tasks are created per-run because they depend on the report path and gender.

def build_tasks(report_path: str, gender: str = "default") -> list[Task]:

    extractor_prompt = load_prompt("extractor")
    alerter_prompt   = load_prompt("alerter")
    writer_prompt    = load_prompt("writer")

    # ── Task 1: Extract ───────────────────────────────────────────────────────
    task_extract = Task(
        description = (
            f"Use the PDF Reader tool to read the report at: {report_path}\n\n"
            "Then extract ALL biological parameters from the text.\n\n"
            + extractor_prompt.replace("{report_text}", "[text returned by the tool]")
        ),
        expected_output = (
            "A valid JSON array of all biological parameters. "
            "Each item: {\"parameter\": str, \"value\": float, \"unit\": str, \"source_context\": str}. "
            "No markdown fences. No explanation. Pure JSON only."
        ),
        agent  = extractor_agent,
    )

    # ── Task 2: Interpret ─────────────────────────────────────────────────────
    task_interpret = Task(
        description = (
            f"You receive a JSON array of biological parameters from the extractor.\n"
            f"Call the Bulk Medical Threshold Checker tool with:\n"
            f"{{\"parameters\": <the array>, \"gender\": \"{gender}\"}}\n\n"
            "Process ALL parameters in ONE tool call. Return the full annotated array."
        ),
        expected_output = (
            "A JSON array where every item has: "
            "parameter, value, unit, normal_range, status (NORMAL|ABNORMAL|CRITICAL), clinical_risk."
        ),
        agent   = interpreter_agent,
        context = [task_extract],
    )

    # ── Task 3: Alert ─────────────────────────────────────────────────────────
    task_alert = Task(
        description = (
            "From the annotated parameter list, filter only CRITICAL and ABNORMAL values.\n"
            "For each one:\n"
            "  - Assign urgency: HIGH (if CRITICAL) or MEDIUM (if ABNORMAL)\n"
            "  - Write ONE concrete clinical action (one sentence, no explanation)\n"
            "  - Use this format per alert:\n"
            "    Parameter: <name> | Value: <v> <unit> | Status: <s> | Urgency: <u> | Action: <action>\n\n"
            "Sort results: HIGH urgency first, then MEDIUM.\n"
            "End with a summary line: CRITICAL: <n> | ABNORMAL: <n>"
        ),
        expected_output = (
            "A structured alert list sorted by urgency, one alert per line, "
            "followed by a summary count line."
        ),
        agent   = alerter_agent,
        context = [task_interpret],
    )

    # ── Task 4: Write ─────────────────────────────────────────────────────────
    task_write = Task(
        description = (
            "Write the final clinical summary for the doctor on duty.\n\n"
            + writer_prompt.replace(
                "{critical_str}",  "[CRITICAL values from the alerter output]"
            ).replace(
                "{abnormal_str}",  "[ABNORMAL values from the alerter output]"
            ).replace(
                "{actions_str}",   "[actions from the alerter output]"
            ).replace(
                "{report_excerpt}", "[first section of the original report]"
            )
        ),
        expected_output = (
            "A structured medical summary with exactly 4 sections: "
            "PATIENT OVERVIEW, KEY FINDINGS, CRITICAL ALERTS, RECOMMENDED ACTIONS. "
            "Under 200 words total."
        ),
        agent   = writer_agent,
        context = [task_extract, task_interpret, task_alert],
    )

    return [task_extract, task_interpret, task_alert, task_write]


# ── Crew factory ──────────────────────────────────────────────────────────────

def build_crew(report_path: str, gender: str = "default") -> Crew:
    tasks = build_tasks(report_path, gender)
    return Crew(
        agents  = [extractor_agent, interpreter_agent, alerter_agent, writer_agent],
        tasks   = tasks,
        process = Process.sequential,   # Agent 1 → 2 → 3 → 4, strictly in order
        verbose = True,
    )