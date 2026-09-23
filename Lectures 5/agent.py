"""Screen-aware PydanticAI agent for the immersive browser chat."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent, ModelMessage, ToolReturn
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from screen_tools import capture_screen


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PROMPT_PATH = APP_DIR / "prompts" / "prompt.md"

_HISTORY_LOCK = threading.Lock()
_MESSAGE_HISTORY: list[ModelMessage] = []


DEFAULT_PROMPT = """
You are an immersive browser assistant. Help the user understand, navigate, and
reason about the web page or PDF visible in the real browser on the left.

Use the look_at_screen tool whenever answering requires knowing what is visible,
including questions about page text, layout, images, charts, forms, errors, or
the current URL. Do not claim to have looked at the screen unless you used the
tool. If the user asks a general question that does not depend on the browser,
answer directly without taking a screenshot.

When you use a screenshot, describe only what you can actually see and clearly
separate observation from inference. Never expose secrets, credentials, or
private data found on screen. Do not click, type into, download from, or submit
anything in the browser; you may explain how the user can do it themselves.
Keep answers helpful and reasonably concise.
""".strip()


def _load_instructions() -> str:
    if PROMPT_PATH.exists():
        prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
        if prompt:
            return prompt
    return DEFAULT_PROMPT


def build_agent() -> Agent[dict[str, Any], str]:
    """Build a PydanticAI agent routed through Portkey to GPT-5.6 Luna."""
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ["PORTKEY_API_KEY"]
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )
    model = OpenAIResponsesModel(
        "gpt-5.6-luna",
        provider=OpenAIProvider(openai_client=client),
    )
    agent = Agent(
        model,
        deps_type=dict[str, Any],
        output_type=str,
        instructions=_load_instructions(),
    )

    @agent.tool(name="look_at_screen")
    def look_at_screen_tool(ctx: RunContext[dict[str, Any]]) -> ToolReturn[Any]:
        """Capture the Browser agent window and inspect its visible content."""
        shot = capture_screen("window")
        ctx.deps["last_shot"] = {
            "captured_at": shot["captured_at"],
            "region": shot["region"],
        }
        ctx.deps.setdefault("tool_events", []).append({"name": "Look at screen"})
        image = BinaryContent(
            data=shot["data"],
            media_type="image/png",
            vendor_metadata={"detail": "high"},
        )
        description = (
            f"Screenshot captured at {shot['captured_at']} from the {shot['region']} region "
            f"({shot['width']}x{shot['height']}). Inspect the attached image."
        )
        return ToolReturn(return_value=[description, image])

    return agent


def run_agent(user_text: str) -> dict[str, Any]:
    """Run one turn and return the shape expected by app.py."""
    message = user_text.strip()
    if not message:
        return {"text": "Please enter a message.", "tool_events": [], "last_shot": None}

    deps: dict[str, Any] = {"tool_events": [], "last_shot": None}
    with _HISTORY_LOCK:
        history = list(_MESSAGE_HISTORY)
        result = build_agent().run_sync(
            message,
            deps=deps,
            message_history=history,
            usage_limits=UsageLimits(request_limit=6, tool_calls_limit=2),
        )
        _MESSAGE_HISTORY.clear()
        _MESSAGE_HISTORY.extend(result.all_messages())

    return {
        "text": result.output,
        "tool_events": deps["tool_events"],
        "last_shot": deps["last_shot"],
    }


def reset_history() -> None:
    """Clear the in-process conversation, useful during local development."""
    with _HISTORY_LOCK:
        _MESSAGE_HISTORY.clear()
