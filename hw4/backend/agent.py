"""Agent wiring: prompt file + model + tools.

How the agent is assembled
--------------------------
1. **Prompt** — `prompts/prompt.md` is read from disk and becomes the system
   prompt. It is the editable half of the agent; growing the file changes the
   agent's behaviour with no code change. A second, dynamic system prompt adds
   who the shopper is, so the file itself stays static and cacheable.

2. **Model** — `gpt-5.6-luna`, reached through Portkey's OpenAI-compatible
   endpoint. PydanticAI's provider takes a preconfigured `AsyncOpenAI` client
   because that is the only hook for Portkey's `x-portkey-provider` header. The
   key is read from the repo-root `.env`; it never appears in source. Luna does
   not support `temperature`, so none is ever set.

3. **Tools** — the four functions in `tools.py`. PydanticAI turns their
   signatures, type hints and docstrings into the tool schemas the model sees,
   which is why those docstrings read as instructions to the model.

Everything is built once and cached: re-reading the prompt and rebuilding the
HTTP client on every message would add latency for no benefit.
"""

import time
from functools import lru_cache
from pathlib import Path

from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import audit
from config import MODEL_ID, PORTKEY_API_KEY, PORTKEY_BASE_URL
from models import ChatDeps, ChatReply, ChatTurn
from tools import ALL_TOOLS

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "prompt.md"

# Keeps one bad question from running up a bill or hanging the chat panel. Headroom
# for a search plus a handful of follow-up lookups; tools are built so a normal
# question needs one or two calls, not one per result.
MAX_TOOL_CALLS = 14

# A broad search can legitimately touch a dozen products. The panel is narrow, so
# cap what gets drawn — the reply text still says what else exists.
MAX_CARDS = 8


class AgentUnavailable(RuntimeError):
    """Raised when the agent cannot be built — almost always a missing API key."""


#: (mtime, text) of the last read, so an edited prompt takes effect without a
#: restart. `uvicorn --reload` only watches .py files, so a plain cache here meant
#: edits to prompt.md were silently ignored by a running server — which defeats the
#: point of keeping the prompt in an editable file.
_prompt_cache: tuple[float, str] | None = None


def load_prompt() -> str:
    """The system prompt, re-read from `prompts/prompt.md` whenever it changes."""
    global _prompt_cache

    if not PROMPT_PATH.exists():
        raise AgentUnavailable(f"System prompt missing at {PROMPT_PATH}")

    mtime = PROMPT_PATH.stat().st_mtime
    if _prompt_cache is not None and _prompt_cache[0] == mtime:
        return _prompt_cache[1]

    text = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise AgentUnavailable(f"System prompt at {PROMPT_PATH} is empty")

    _prompt_cache = (mtime, text)
    return text


@lru_cache(maxsize=1)
def get_model() -> OpenAIResponsesModel:
    if not PORTKEY_API_KEY:
        raise AgentUnavailable("PORTKEY_API_KEY is missing. Add it to the repo-root .env file.")

    client = AsyncOpenAI(
        api_key=PORTKEY_API_KEY,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_ID, provider=OpenAIProvider(openai_client=client))


@lru_cache(maxsize=1)
def get_agent() -> Agent[ChatDeps, str]:
    agent = Agent(get_model(), deps_type=ChatDeps, tools=ALL_TOOLS, retries=2)

    @agent.instructions
    def file_prompt() -> str:
        """Read per run, not captured at construction, so editing prompts/prompt.md
        changes behaviour on the next message."""
        return load_prompt()

    @agent.instructions
    def shopper_context(ctx: RunContext[ChatDeps]) -> str:
        """Who is asking — injected per run rather than written into the prompt file.

        This is why identity lives in deps: the file on disk is one static document
        shared by every shopper, and no individual's name or email is ever baked
        into it.
        """
        deps = ctx.deps
        if not deps.logged_in:
            return (
                "The shopper is browsing as a GUEST. You do not know their name, email, "
                "or anything they have said in the past. Do not guess, and do not ask "
                "for personal details — they can create an account from the navigation "
                "bar if they want their chats remembered."
            )

        lines = [
            f"The shopper is LOGGED IN. Their first name is {deps.first_name}.",
            "Greet them by name on the first reply of a conversation, not in every message.",
        ]
        if deps.member_since:
            lines.append(f"They have had an account since {deps.member_since[:10]}.")
        lines.append(
            "Their full name and email are available via the get_customer tool if they "
            "ask about their own account. Never read their email out unprompted."
        )
        return " ".join(lines)

    @agent.instructions
    def page_context(ctx: RunContext[ChatDeps]) -> str:
        """What the shopper is looking at — the other half of resolving "this"."""
        deps = ctx.deps
        if deps.page_product_id and deps.page_product_name:
            return (
                f"RIGHT NOW the shopper is viewing the product page for "
                f"\"{deps.page_product_name}\" (id: {deps.page_product_id}). If they say "
                '"this", "it", or "that one" without naming a product, they mean this '
                "one — call get_current_product to get its details rather than asking "
                "which they meant."
            )
        if deps.page_path:
            where = {
                "/": "the home page",
                "/products": "the storeroom, browsing the full catalogue",
                "/about": "the About Us page",
            }.get(deps.page_path, f"the page {deps.page_path}")
            return (
                f"The shopper is on {where}. They are not looking at any one product, so "
                'if they say "this" without naming something, ask which item they mean.'
            )
        return ""

    return agent


def _is_content_filter(exc: ModelHTTPError) -> bool:
    body = exc.body if isinstance(exc.body, dict) else {}
    error = body.get("error", body) if isinstance(body, dict) else {}
    haystack = f"{error.get('code', '')} {error.get('message', '')}".lower()
    return exc.status_code == 400 and ("content_filter" in haystack or "content management" in haystack)


def _to_messages(history: list[ChatTurn]) -> list[ModelMessage]:
    """Replay prior turns as PydanticAI messages so the agent has the thread.

    History arrives from the browser rather than the database for now; Problem 8
    moves it server-side into `chat_messages`, which is the only reason this takes
    a list instead of reading storage itself.
    """
    messages: list[ModelMessage] = []
    for turn in history:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return messages


async def run_chat(
    message: str,
    history: list[ChatTurn] | None = None,
    deps: ChatDeps | None = None,
) -> ChatReply:
    """One turn: send a message, get the reply plus whatever products were looked up."""
    deps = deps or ChatDeps()
    started = time.monotonic()

    def record(stop_reason: str, reply: str) -> None:
        """One audit line per turn, whatever the outcome.

        Written here rather than in main.py so every exit path — success, refusal,
        tool-limit, error — is covered by the same code.
        """
        audit.append(
            {
                "event": "agent_turn",
                "user_id": deps.user_id,  # null for a guest; never the email
                "page": deps.page_path or None,
                "message": audit.short(message),
                "model": MODEL_ID,
                "tools": deps.events,
                "tool_calls": len(deps.events),
                "stop_reason": stop_reason,
                "products_returned": len(deps.shown),
                "reply": audit.short(reply),
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )

    try:
        result = await get_agent().run(
            message,
            deps=deps,
            message_history=_to_messages(history or []),
            usage_limits=UsageLimits(tool_calls_limit=MAX_TOOL_CALLS),
        )
    except AgentUnavailable as exc:
        record("agent_unavailable", str(exc))
        raise
    except ModelHTTPError as exc:
        # The provider runs its own content filter ahead of the model, and it
        # rejects the whole request with a 400 rather than letting the model
        # answer. That is a refusal, not an outage, so answer like one instead of
        # showing the shopper a broken panel.
        if _is_content_filter(exc):
            reply = (
                "That one's outside what I can help with. Ask me about Yale gear "
                "— sizes, colors, prices — and I'm all yours."
            )
            record("content_filter", reply)
            return ChatReply(
                reply=reply,
                products=[],
                tools_used=deps.tools_used,
                model=MODEL_ID,
            )
        record("model_http_error", f"{exc.status_code}")
        raise
    except UsageLimitExceeded:
        # The agent fanned out past the cap. Whatever it already looked up is real,
        # so show that rather than throwing the turn away — a broken panel is a far
        # worse answer than a partial one.
        cards = list(deps.shown.values())
        if cards:
            names = ", ".join(c.name for c in cards[:5])
            reply = (
                f"That took more digging than I could do in one go. Here's what I found "
                f"so far: {names}. Ask me about any one of them and I'll get you exact "
                "sizes and stock."
            )
        else:
            reply = (
                "That one got away from me — try asking about one thing at a time, "
                "like \"sports tees in small\"."
            )
        record("tool_limit_exceeded", reply)
        return ChatReply(
            reply=reply,
            products=cards[:MAX_CARDS],
            query=deps.search_query,
            total_found=deps.total_found,
            tools_used=deps.tools_used,
            model=MODEL_ID,
        )

    except Exception as exc:  # noqa: BLE001 - audited, then re-raised unchanged
        record("error", f"{type(exc).__name__}")
        raise

    record("completed", result.output)
    return ChatReply(
        reply=result.output,
        products=list(deps.shown.values())[:MAX_CARDS],
        query=deps.search_query,
        total_found=deps.total_found,
        tools_used=deps.tools_used,
        model=MODEL_ID,
    )
