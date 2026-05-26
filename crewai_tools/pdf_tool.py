# crewai_tools/pdf_tool.py
#
# Wraps tools/pdf_reader.py as a CrewAI BaseTool.
# The extractor agent uses this to read the report before extracting values.

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from crewai.tools import BaseTool
from tools.pdf_reader import read_report


class PDFReaderTool(BaseTool):
    name: str = "PDF and Text Report Reader"
    description: str = (
        "Reads a medical report file (.pdf or .txt) and returns its full raw text. "
        "Input: absolute or relative file path string. "
        "Output: full text content of the report."
    )

    def _run(self, file_path: str) -> str:
        try:
            return read_report(file_path.strip())
        except Exception as e:
            return f"ERROR reading file: {e}"