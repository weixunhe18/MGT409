"""Minimal Portkey smoke test for GPT-5.6 Luna.

Run from this directory after installing requirements.txt:
    python test_luna.py
"""

from pathlib import Path
import os

from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

portkey_api_key = os.getenv("PORTKEY_API_KEY")
if not portkey_api_key:
    raise RuntimeError("PORTKEY_API_KEY was not found in the root .env file")

client = OpenAI(
    api_key=portkey_api_key,
    base_url="https://api.portkey.ai/v1",
    default_headers={"x-portkey-provider": "openai"},
)

response = client.responses.create(
    model="gpt-5.6-luna",
    input="Reply with exactly: Portkey and Luna are connected.",
    reasoning={"effort": "none"},
    max_output_tokens=32,
)

print(response.output_text)
