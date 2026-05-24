from pypdf import PdfReader
import os

def read_report(path: str) -> str:
    """
    Reads a medical report from either:
    - a .pdf file  → extracts text via pypdf
    - a .txt file  → reads directly
    Returns raw text string.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Report not found: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()

    elif ext == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .pdf or .txt")