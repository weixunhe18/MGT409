"""Shared plumbing: the model, the MCP toolset, the spend-limit guard, and the logs.

Every shop fact comes from the campus-customs MCP server. Nothing here reads the database directly.
"""

from datetime import datetime
from pathlib import Path
import json
import os
import uuid

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ModelRequest, ModelResponse
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from backend.models import AgentReport, TeamDeps


HW_ROOT = Path(__file__).resolve().parents[1]
# Reads hw5/.env if present, otherwise the repository root .env.
load_dotenv(HW_ROOT / ".env")
load_dotenv(HW_ROOT.parent / ".env")

MODEL_ID = "gpt-5.6-luna"
DB_PATH = Path(os.environ.get("CAMPUS_DB_PATH", HW_ROOT / "data" / "campus_customs_new.db"))
DECISION_LOG = Path(os.environ.get("DECISION_LOG", HW_ROOT / "output" / "decision_log.json"))
AUDIT_TRAIL = Path(os.environ.get("AUDIT_TRAIL", HW_ROOT / "output" / "audit_trail.json"))
PROMPTS = Path(__file__).parent / "prompts"

# Tools that move money out. The guard asks the server's check_spend_limit before each one.
MONEY_OUT_TOOLS = {"pay_rent", "pay_invoice", "record_payment"}

# Token guardrails, per agent run.
WORKER_LIMITS = UsageLimits(request_limit=10, tool_calls_limit=8, total_tokens_limit=60_000)
BOSS_LIMITS = UsageLimits(request_limit=3, total_tokens_limit=20_000)

model = OpenAIResponsesModel(
    MODEL_ID,
    provider=OpenAIProvider(
        openai_client=AsyncOpenAI(
            api_key=os.environ["PORTKEY_API_KEY"],
            base_url="https://api.portkey.ai/v1",
            default_headers={"x-portkey-provider": "openai"},
        )
    ),
)
# No temperature for gpt-5.6-luna.
model_settings = OpenAIResponsesModelSettings(openai_reasoning_effort="low", max_tokens=2_000)


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text()


def _append_json(path: Path, entry: dict) -> None:
    """Append one entry to a JSON-array file, keeping everything already there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = json.loads(path.read_text()) if path.exists() and path.read_text().strip() else []
    entries.append(entry)
    path.write_text(json.dumps(entries, indent=2, default=str))


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log_decision(ticket_id: int, decided_by: str, kind: str, **detail) -> None:
    """Decision log: who made each call (an agent or 'boss')."""
    _append_json(DECISION_LOG, {"ts": now(), "ticket_id": ticket_id, "decided_by": decided_by,
                                "kind": kind, **detail})


# --- MCP ---------------------------------------------------------------------


def mcp_transport() -> PythonStdioTransport:
    return PythonStdioTransport(
        HW_ROOT / "mcp_server" / "server.py",
        env={**os.environ, "CAMPUS_DB_PATH": str(DB_PATH)},
        cwd=str(HW_ROOT),
    )


async def mcp_call(name: str, args: dict | None = None) -> dict:
    """Call one campus-customs tool outside an agent run (used by the boss loop)."""
    async with Client(mcp_transport()) as client:
        return (await client.call_tool(name, args or {})).data


async def guard_tool_call(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict):
    """Runs before every agent MCP call: enforces the spend limit and logs who made the call."""
    deps = ctx.deps
    decided_by = deps.agent

    if name in MONEY_OUT_TOOLS:
        check = await call_tool("check_spend_limit", {
            "tool": name, "account": args.get("account", "checking"),
            **{k: args[k] for k in ("lease_id", "invoice_id", "amount") if k in args},
        })
        approval = deps.boss_approval
        if isinstance(check, dict) and check.get("needs_boss_approval"):
            if approval is None or not approval.approved or check["amount"] > approval.max_amount:
                result = {"status": "needs_boss_approval", "tool": name, "amount": check["amount"],
                          "limit": check["limit"],
                          "message": f"{check['amount']:.2f} is over your limit of {check['limit']:.2f} "
                                     "(80% of the account). Return needs_boss_approval."}
                log_decision(deps.ticket_id, deps.agent, "blocked_over_limit", tool=name, args=args,
                             amount=check["amount"], limit=check["limit"])
                deps.tool_calls.append({"tool": name, "args": args, "result": result})
                return result
            decided_by = "boss"
        # Agents only prepare payments. A human approves on the desk board (POST /payments/{id}/approve),
        # and only that route moves cash.
        clean = {k: v for k, v in args.items() if k not in ("approved_by", "ticket_id")}
        purpose = args.get("description") or f"{name} for ticket {deps.ticket_id}"
        result = await call_tool("prepare_payment", {
            "tool": name, "args": clean, "amount": check["amount"], "purpose": purpose,
            "prepared_by": "boss" if decided_by == "boss" else f"{deps.agent} agent",
            "ticket_id": deps.ticket_id,
        })
        log_decision(deps.ticket_id, decided_by, "payment_prepared", agent=deps.agent, tool=name,
                     args=clean, result=result)
        deps.tool_calls.append({"tool": name, "args": clean, "result": result})
        return result

    result = await call_tool(name, args)
    if name == "check_spend_limit" and isinstance(result, dict) and result.get("needs_boss_approval"):
        approval = deps.boss_approval
        if approval and approval.approved and result["amount"] <= approval.max_amount:
            result = {**result, "boss_approved": True,
                      "message": f"Boss approved up to {approval.max_amount:.2f}. Go ahead and pay."}
    log_decision(deps.ticket_id, decided_by, "tool_call", agent=deps.agent, tool=name, args=args, result=result)
    deps.tool_calls.append({"tool": name, "args": args, "result": result})
    return result


def campus_tools(*allowed: str):
    """The campus-customs MCP server, limited to the tools one agent may use."""
    toolset = MCPToolset(mcp_transport(), process_tool_call=guard_tool_call)
    return toolset.filtered(lambda ctx, tool_def: tool_def.name in allowed)


def make_worker(name: str, *tools: str) -> Agent[TeamDeps, AgentReport]:
    return Agent(
        model,
        name=name,
        instructions=load_prompt(name),
        deps_type=TeamDeps,
        output_type=AgentReport,
        toolsets=[campus_tools(*tools)],
        model_settings=model_settings,
    )


# --- Audit trail -------------------------------------------------------------


def _parts(message) -> list[dict]:
    """Flatten a model request/response into auditable parts."""
    out = []
    for part in message.parts:
        kind = part.part_kind
        entry = {"part": kind}
        if kind in ("tool-call", "tool-return", "retry-prompt"):
            entry["tool"] = getattr(part, "tool_name", None)
            entry["tool_call_id"] = getattr(part, "tool_call_id", None)
        if kind == "tool-call":
            entry["args"] = part.args_as_dict()
        elif kind in ("tool-return", "retry-prompt", "user-prompt", "text"):
            entry["content"] = part.content
        elif kind == "system-prompt":
            entry["content"] = "(system prompt omitted; see backend/prompts/)"
        out.append(entry)
    return out


async def run_audited(agent: Agent, prompt: str, *, ticket_id: int, role: str,
                      limits: UsageLimits, deps=None):
    """Run an agent step by step, appending every loop step to the audit trail as it happens."""
    run_id = uuid.uuid4().hex[:8]
    base = {"ticket_id": ticket_id, "agent": role, "run_id": run_id, "model": MODEL_ID}
    async with agent.iter(prompt, deps=deps, usage_limits=limits) as run:
        step = 0
        async for node in run:
            step += 1
            entry = {"ts": now(), **base, "step": step, "node": type(node).__name__}
            if Agent.is_model_request_node(node):
                entry["sent_to_model"] = _parts(node.request)
            elif Agent.is_call_tools_node(node):
                entry["model_response"] = _parts(node.model_response)
            elif Agent.is_end_node(node):
                output = node.data.output
                entry["output"] = output.model_dump() if hasattr(output, "model_dump") else output
            elif Agent.is_user_prompt_node(node):
                entry["user_prompt"] = prompt
            usage = run.usage
            entry["usage_so_far"] = {"requests": usage.requests, "input_tokens": usage.input_tokens,
                                     "output_tokens": usage.output_tokens}
            _append_json(AUDIT_TRAIL, entry)
    return run.result
