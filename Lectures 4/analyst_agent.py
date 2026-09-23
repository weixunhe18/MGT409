"""PydanticAI stock analyst with audited market-data and native web search tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelMessagesTypeAdapter, RunContext
from pydantic_ai.capabilities import NativeTool
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.native_tools import WebSearchTool
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits
import yfinance as yf


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PORTFOLIO_PATH = APP_DIR / "portfolio.json"
AUDIT_PATH = APP_DIR / "audit.jsonl"
ALLOWED_TICKERS = {"AAPL", "MSFT", "NVDA", "GOOGL", "JPM"}


def load_portfolio() -> dict[str, Any]:
    """Load the current local portfolio state; no tool can modify it."""
    with PORTFOLIO_PATH.open(encoding="utf-8") as portfolio_file:
        return json.load(portfolio_file)


def audit(event: str, **details: Any) -> None:
    """Append observable events only; never write secrets or hidden reasoning."""
    record = {"event": event, "date": date.today().isoformat(), **details}
    with AUDIT_PATH.open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(record, default=str) + "\n")


@dataclass
class AnalystDeps:
    portfolio: dict[str, Any]


def _validate_price_request(ticker: str, start: str, stop: str) -> tuple[str, date, date]:
    symbol = ticker.strip().upper()
    if symbol not in ALLOWED_TICKERS:
        raise ValueError(f"{symbol} is outside the approved universe: {', '.join(sorted(ALLOWED_TICKERS))}.")
    start_date = date.fromisoformat(start)
    stop_date = date.fromisoformat(stop)
    if start_date >= stop_date:
        raise ValueError("start must be before stop (both YYYY-MM-DD).")
    if (stop_date - start_date).days > 366:
        raise ValueError("Request at most 366 calendar days of price history at a time.")
    return symbol, start_date, stop_date


def get_stock_price(ticker: str, start: str, stop: str) -> dict[str, Any]:
    """Get verified daily OHLCV data from yfinance for an approved ticker and date range."""
    symbol, start_date, stop_date = _validate_price_request(ticker, start, stop)
    audit("tool_call", tool="get_stock_price", ticker=symbol, start=start, stop=stop)
    try:
        history = yf.Ticker(symbol).history(
            start=start_date.isoformat(), end=stop_date.isoformat(), auto_adjust=False
        )
    except Exception as exc:  # yfinance errors are external-data errors, not price estimates.
        audit("tool_error", tool="get_stock_price", ticker=symbol, error=str(exc))
        raise RuntimeError("yfinance could not retrieve price data. Do not infer or invent a price.") from exc

    if history.empty:
        audit("tool_observation", tool="get_stock_price", ticker=symbol, rows=0)
        return {
            "ticker": symbol,
            "start": start,
            "stop": stop,
            "source": "yfinance",
            "rows": [],
            "note": "No observations were returned. Do not infer a price.",
        }

    rows = []
    for timestamp, row in history.tail(100).iterrows():
        rows.append(
            {
                "date": timestamp.date().isoformat(),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            }
        )
    audit("tool_observation", tool="get_stock_price", ticker=symbol, rows=len(rows))
    return {"ticker": symbol, "start": start, "stop": stop, "source": "yfinance", "rows": rows}


def _native_tool_events(messages: list[Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for message in messages:
        for part in getattr(message, "parts", []):
            if getattr(part, "tool_name", None) == "web_search":
                events.append({"tool": "web_search", "args": str(getattr(part, "args", ""))[:800]})
    return events


def build_agent() -> Agent[AnalystDeps, str]:
    """Create an OpenAI Responses-compatible PydanticAI agent routed through Portkey."""
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ["PORTKEY_API_KEY"]
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )
    model = OpenAIResponsesModel(
        "gpt-5.6-luna", provider=OpenAIProvider(openai_client=client)
    )
    agent = Agent(
        model,
        deps_type=AnalystDeps,
        instructions=(
            "You are a careful stock-analysis research assistant. The approved universe is "
            "AAPL, MSFT, NVDA, GOOGL, and JPM. Current portfolio state is available in dependencies. "
            "Use get_stock_price for all historical or current-price claims; never invent prices or dates. "
            "Use the native web_search tool for news or time-sensitive facts when useful, and identify it as web research. "
            "Do not place trades, give personalized buy/sell instructions, promise returns, assist market manipulation, "
            "or claim certainty. Refuse those asks briefly and offer neutral education or research instead. "
            "Finish with a concise answer once the question is answered; do not repeat tool calls. "
            "Mention data limits, market-data timing, and uncertainty where relevant."
        ),
        capabilities=[
            NativeTool(WebSearchTool(search_context_size="medium", max_uses=2, external_web_access=True))
        ],
    )

    @agent.tool(name="get_stock_price")
    def get_stock_price_tool(
        _ctx: RunContext[AnalystDeps], ticker: str, start: str, stop: str
    ) -> dict[str, Any]:
        """Get daily price data for an approved ticker. Dates must be YYYY-MM-DD; stop is exclusive."""
        return get_stock_price(ticker, start, stop)

    return agent


def run_analysis(prompt: str, history_payload: list[dict[str, Any]] | None, portfolio: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Run one bounded turn and return response text plus serialized PydanticAI history."""
    history = ModelMessagesTypeAdapter.validate_python(history_payload or [])
    audit("run_started", prompt=prompt[:1200], history_messages=len(history), portfolio_as_of=portfolio.get("as_of"))
    try:
        result = build_agent().run_sync(
            prompt,
            deps=AnalystDeps(portfolio=portfolio),
            message_history=history,
            usage_limits=UsageLimits(request_limit=8, tool_calls_limit=5),
        )
        messages = result.all_messages()
        events = _native_tool_events(messages)
        for event in events:
            audit("native_tool_call", **event)
        usage = result.usage
        audit(
            "run_finished",
            usage={"requests": usage.requests, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
            native_tool_events=len(events),
            note="Audit records observable events and summaries, not private chain-of-thought.",
        )
        return result.output, json.loads(result.all_messages_json())
    except Exception as exc:
        audit("run_error", error=type(exc).__name__, message=str(exc)[:800])
        raise
