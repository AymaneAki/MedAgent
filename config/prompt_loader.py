# config/prompt_loader.py

import os

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

def load_prompt(name: str) -> str:
    """
    Loads a prompt template from config/prompts/<name>.txt
    Example: load_prompt("extractor") 
    """
    path = os.path.join(PROMPTS_DIR, f"{name}.txt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()