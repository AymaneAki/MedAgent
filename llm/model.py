from openai import OpenAI
import os

def get_llm_client():
    """
    Returns an OpenAI-compatible client pointing to
    the local BitNet server running in Docker.
    BitNet's llama.cpp server exposes an OpenAI-compatible API.
    """
    return OpenAI(
        base_url=os.getenv("BITNET_BASE_URL", "http://localhost:11434") + "/v1",
        api_key="not-needed"   
    )

def call_llm(prompt: str, max_tokens: int = 512, temperature: float = 0.1) -> str:
    """
    Single entry point for all agents to call the LLM.
    Swap the model or URL here agents never change.
    """
    client = get_llm_client()

    response = client.chat.completions.create(
        model=os.getenv("BITNET_MODEL", "bitnet-b1.58-2b-4t"),
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    return response.choices[0].message.content.strip()

