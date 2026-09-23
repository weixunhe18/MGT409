"""PydanticAI sports video judge routed through Portkey."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Union

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent, ToolReturn
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from models import DunkVerdict, FoulVerdict
from video_tools import call_foul, describe_video, sample_frames, score_dunk

HERE = Path(__file__).resolve().parent
PROMPT = (HERE / "prompts" / "prompt.md").read_text(encoding="utf-8")
Verdict = Union[DunkVerdict, FoulVerdict]


def _load_key() -> str:
    # Local .env wins; parent .env is the fallback for Lecture 6 projects.
    load_dotenv(HERE.parent / ".env")
    load_dotenv(HERE / ".env", override=True)
    return os.environ["PORTKEY_API_KEY"]


def build_agent() -> Agent[dict[str, Any], Verdict]:
    client = AsyncOpenAI(
        api_key=_load_key(),
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )
    model = OpenAIResponsesModel("gpt-5.6-luna", provider=OpenAIProvider(openai_client=client))
    agent = Agent(model, deps_type=dict[str, Any], output_type=Verdict, instructions=PROMPT)

    def mark(ctx: RunContext[dict[str, Any]], name: str) -> None:
        ctx.deps.setdefault("tool_events", []).append({"name": name})
        callback = ctx.deps.get("on_tool")
        if callback:
            callback(name)

    @agent.tool(name="sample_frames")
    def sample_tool(ctx: RunContext[dict[str, Any]], video_path: str, every_n_sec: float = 0.5, max_frames: int = 16):
        mark(ctx, "sample_frames")
        return sample_frames(video_path, every_n_sec, max_frames)

    @agent.tool(name="describe_video")
    def describe_tool(ctx: RunContext[dict[str, Any]], frame_paths: list[str], clip_label: str) -> ToolReturn[Any]:
        mark(ctx, "describe_video")
        data = describe_video(frame_paths, clip_label)
        parts: list[Any] = [json.dumps(data)]
        for relative in frame_paths:
            path = HERE / relative
            if path.is_file():
                parts.append(BinaryContent(data=path.read_bytes(), media_type="image/png"))
        return ToolReturn(return_value=parts)

    @agent.tool(name="score_dunk")
    def dunk_tool(ctx: RunContext[dict[str, Any]], frame_paths: list[str], description: str, clip_label: str) -> DunkVerdict:
        mark(ctx, "score_dunk")
        return score_dunk(frame_paths, description, clip_label)

    @agent.tool(name="call_foul")
    def foul_tool(ctx: RunContext[dict[str, Any]], frame_paths: list[str], description: str, clip_label: str) -> FoulVerdict:
        mark(ctx, "call_foul")
        return call_foul(frame_paths, description, clip_label)

    return agent


def run_agent(video_path: str, on_tool: Callable[[str], None] | None = None) -> dict[str, Any]:
    deps: dict[str, Any] = {"tool_events": [], "on_tool": on_tool}
    try:
        result = build_agent().run_sync(
            f"Judge this sports clip. Video path: {Path(video_path).resolve()}",
            deps=deps,
        )
        return {"verdict": result.output, "tool_events": deps["tool_events"]}
    except Exception as exc:
        return {"verdict": None, "error": str(exc), "tool_events": deps["tool_events"]}
