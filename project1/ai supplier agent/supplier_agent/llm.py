"""LLM access + token metering.

Live mode calls gpt-6-luna through Portkey's OpenAI-compatible Responses API with the
course key (same headers as the course starter repo), using only the standard library.
Mock mode runs the agents' deterministic stand-ins and records *estimated* tokens, so
the app works offline with no key.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class LLMError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


def cost_usd(prices: dict, input_tokens: int, cached_tokens: int, output_tokens: int,
             cache_write_tokens: int = 0) -> float:
    """Lecture 11 formula: input_tokens includes cache reads and cache writes."""
    uncached = max(0, input_tokens - cached_tokens - cache_write_tokens)
    total = (
        uncached * prices["input"]
        + cached_tokens * prices["cached_input"]
        + cache_write_tokens * prices.get("cache_write", prices["input"])
        + output_tokens * prices["output"]
    )
    return total / 1_000_000


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text or "") / 4))


@dataclass
class Meter:
    """Per-email meter. Enforces the call cap and the per-email and daily dollar caps."""

    prices: dict
    max_calls: int = 6
    per_email_budget_usd: float = 0.05
    daily_spent_usd: float = 0.0
    daily_budget_usd: float = 1.0
    calls: list = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(c["cost_usd"] for c in self.calls)

    def totals(self) -> dict:
        return {
            "calls": len(self.calls),
            "input_tokens": sum(c["input_tokens"] for c in self.calls),
            "cached_tokens": sum(c["cached_tokens"] for c in self.calls),
            "output_tokens": sum(c["output_tokens"] for c in self.calls),
            "cost_usd": round(self.total_cost, 6),
            "estimated": any(c["estimated"] for c in self.calls),
        }

    def check_before_call(self, agent: str) -> None:
        if len(self.calls) >= self.max_calls:
            raise BudgetExceeded(f"{agent}: max {self.max_calls} model calls per email reached (loop guard)")
        if self.total_cost >= self.per_email_budget_usd:
            raise BudgetExceeded(f"{agent}: per-email budget ${self.per_email_budget_usd:.2f} reached")
        if self.daily_spent_usd + self.total_cost >= self.daily_budget_usd:
            raise BudgetExceeded(f"{agent}: daily budget ${self.daily_budget_usd:.2f} reached")

    def record(self, agent: str, input_tokens: int, cached_tokens: int, output_tokens: int,
               ms: int, estimated: bool, model: str) -> dict:
        call = {
            "agent": agent,
            "model": model,
            "input_tokens": int(input_tokens),
            "cached_tokens": int(cached_tokens),
            "output_tokens": int(output_tokens),
            "cost_usd": round(cost_usd(self.prices, input_tokens, cached_tokens, output_tokens), 8),
            "ms": int(ms),
            "estimated": estimated,
        }
        self.calls.append(call)
        return call


def parse_json_object(text: str) -> dict:
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("model did not return JSON") from None
        try:
            obj = json.loads(s[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"model returned invalid JSON: {exc}") from None
    if not isinstance(obj, dict):
        raise LLMError("model JSON was not an object")
    return obj


def extract_output_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"]:
        return data["output_text"]
    parts: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") in ("output_text", "text"):
                parts.append(str(content.get("text") or ""))
    if parts:
        return "".join(parts)
    # chat/completions-shaped fallback
    for choice in data.get("choices") or []:
        msg = (choice or {}).get("message") or {}
        if msg.get("content"):
            return str(msg["content"])
    return ""


def parse_usage(data: dict) -> tuple[int, int, int]:
    usage = data.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    cached = int(details.get("cached_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    return input_tokens, cached, output_tokens


class MockLLM:
    """Offline stand-in. Agents run deterministic heuristics; this only meters estimates."""

    live = False

    def __init__(self, model: str = "mock (offline heuristics)"):
        self.model = model

    def record_estimate(self, meter: Meter, agent: str, instructions: str, input_text: str, output_obj) -> dict:
        meter.check_before_call(agent)
        out_text = json.dumps(output_obj, ensure_ascii=False)
        return meter.record(agent, estimate_tokens(instructions) + estimate_tokens(input_text), 0,
                            estimate_tokens(out_text), 0, True, self.model)


class PortkeyLLM:
    """gpt-6-luna via Portkey (OpenAI Responses API). Standard library only."""

    live = True

    def __init__(self, api_key: str, base_url: str = "https://api.portkey.ai/v1", model: str = "gpt-6-luna",
                 provider: str = "openai", reasoning_effort: str = "", timeout: int = 90):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout

    def complete_json(self, *, agent: str, instructions: str, input_text: str, meter: Meter,
                      max_output_tokens: int = 4000) -> tuple[dict, dict]:
        meter.check_before_call(agent)
        payload: dict = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
            "text": {"format": {"type": "json_object"}},
        }
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        t0 = time.perf_counter()
        data = self._post(payload)
        ms = int((time.perf_counter() - t0) * 1000)
        input_tokens, cached, output_tokens = parse_usage(data)
        call = meter.record(agent, input_tokens, cached, output_tokens, ms, False, self.model)
        status = str(data.get("status") or "completed")
        if status != "completed":
            details = data.get("incomplete_details")
            reason = details.get("reason", "") if isinstance(details, dict) else ""
            raise LLMError(f"{agent}: response status '{status}'" + (f" ({reason})" if reason else "")
                           + ". Reasoning may have used up max_output_tokens; try REASONING_EFFORT=low.")
        text = extract_output_text(data)
        if not text:
            raise LLMError(f"{agent}: empty model response (status={data.get('status')})")
        return parse_json_object(text), call

    def _post(self, payload: dict) -> dict:
        last_error = "unknown error"
        for attempt in range(3):
            request = urllib.request.Request(
                self.base_url + "/responses",
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "x-portkey-provider": self.provider,
                    # Portkey's Cloudflare front rejects urllib's default "Python-urllib" agent (403, code 1010).
                    "User-Agent": "supplier-whisperer/0.1",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:400]
                last_error = f"HTTP {exc.code} from Portkey: {detail}"
                if exc.code == 400 and "text" in payload and attempt == 0:
                    # Some gateways/models reject JSON mode; retry once without it (prompt still asks for JSON).
                    payload = {k: v for k, v in payload.items() if k != "text"}
                    continue
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(last_error) from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = f"network error talking to Portkey: {getattr(exc, 'reason', exc)}"
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(last_error) from None
            except json.JSONDecodeError:
                raise LLMError("Portkey returned a non-JSON response") from None
        raise LLMError(last_error)
