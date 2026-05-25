from openai import OpenAI
import os
import sys
import logging
import socket
from urllib.parse import urlparse
from pathlib import Path

# Set up simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MedAgent.LLM")

# Load dotenv if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import mock fallback
from llm.fallback import fallback_call_llm

def is_server_online(url_str: str) -> bool:
    """
    Rapidly checks if a host and port are online using a TCP socket.
    Avoids long connection timeouts in external libraries.
    """
    try:
        parsed = urlparse(url_str)
        host = parsed.hostname
        port = parsed.port
        if not host:
            return False
        if not port:
            port = 443 if parsed.scheme == "https" else 80
            
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)  # 200ms timeout
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def call_llm(prompt: str, max_tokens: int = 512, temperature: float = 0.1) -> str:
    """
    Core entrypoint for all medical agents. Tries:
    1. Local BitNet server (Docker) - only if online
    2. Cloud Gemini API via OpenAI-compatible endpoint - only if API key present
    3. Cloud OpenAI API - only if API key present
    4. Smart clinical rule-based mock engine
    """
    
    # ── Option A: Local BitNet Server (Docker) ──
    bitnet_url = os.getenv("BITNET_BASE_URL", "http://localhost:11434")
    bitnet_model = os.getenv("BITNET_MODEL", "bitnet-b1.58-2b-4t")
    
    if is_server_online(bitnet_url):
        try:
            logger.info(f"Connecting to local BitNet server at {bitnet_url}...")
            client = OpenAI(
                base_url=bitnet_url.rstrip('/') + "/v1",
                api_key="not-needed",
                timeout=5.0
            )
            response = client.chat.completions.create(
                model=bitnet_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            logger.info("Successfully received response from local BitNet server.")
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Local BitNet server connection failed: {e}")
    else:
        logger.info(f"Local BitNet server at {bitnet_url} is offline. Skipping.")
        
    # ── Option B: Google Gemini API (via OpenAI-compatible proxy) ──
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            logger.info("Connecting to Google Gemini API via OpenAI SDK...")
            client = OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=gemini_key,
                timeout=15.0
            )
            response = client.chat.completions.create(
                model="gemini-1.5-flash",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            logger.info("Successfully received response from Gemini API.")
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}")

    # ── Option C: OpenAI Cloud API ──
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            logger.info("Connecting to OpenAI Cloud API...")
            client = OpenAI(
                api_key=openai_key,
                timeout=15.0
            )
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4-turbo"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            logger.info("Successfully received response from OpenAI Cloud API.")
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"OpenAI API call failed: {e}")

    # ── Option D: Smart Clinical Fallback Simulation ──
    logger.debug("No active LLM endpoints available or all connections failed. Falling back to local smart clinical rule-based engine.")
    return fallback_call_llm(prompt)


