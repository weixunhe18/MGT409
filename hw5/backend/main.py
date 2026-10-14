"""FastAPI routes for the Campus Customs desk board.

From the backend/ folder:

    uvicorn main:app --reload --port 8000

Every shop fact goes through the campus-customs MCP server; this file never opens the database.
"""

from pathlib import Path
import json
import os
import sys

# Started from backend/ as `uvicorn main:app`, so put the homework root on the path for `backend.*` imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.boss import handle_ticket
from backend.common import AUDIT_TRAIL, log_decision, mcp_call
from backend.models import TicketOutcome


app = FastAPI(title="Campus Customs desk")
# Only the dashboard (Vite dev server, `npm run dev` in frontend/) may call these routes from a browser.
# Add more origins with DESK_ORIGINS="http://host:port,..." if the board runs somewhere else.
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"] + [
    o for o in os.environ.get("DESK_ORIGINS", "").split(",") if o
]
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])


class ApproveBody(BaseModel):
    approved_by: str = "human"


class RejectBody(BaseModel):
    rejected_by: str = "human"
    reason: str


def _check(result: dict) -> dict:
    if isinstance(result, dict) and result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.get("/tickets")
async def list_tickets() -> dict:
    """The tickets and whether each is open or resolved."""
    return await mcp_call("list_tickets")


@app.post("/tickets/{ticket_id}/run", response_model=TicketOutcome)
async def run_ticket(ticket_id: int) -> TicketOutcome:
    """Run the agent team on one ticket. Takes a minute or so."""
    try:
        return await handle_ticket(ticket_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _events_from_entry(entry: dict) -> list[dict]:
    """Turn one audit-trail step into board events: what the agent said and which tools it used."""
    base = {"ts": entry["ts"], "ticket_id": entry["ticket_id"], "agent": entry["agent"],
            "run_id": entry["run_id"], "step": entry["step"]}
    events = []
    for part in entry.get("model_response", []):
        if part["part"] == "text" and part.get("content"):
            events.append({**base, "type": "said", "content": part["content"]})
        elif part["part"] == "tool-call" and part["tool"] != "final_result":
            events.append({**base, "type": "tool_call", "tool": part["tool"], "args": part.get("args")})
    for part in entry.get("sent_to_model", []):
        if part["part"] == "tool-return" and part["tool"] != "final_result":
            events.append({**base, "type": "tool_result", "tool": part["tool"], "content": part.get("content")})
    if "output" in entry:
        out = entry["output"]
        said = (out.get("customer_message") or out.get("summary") or out.get("reasoning")
                if isinstance(out, dict) else str(out))
        events.append({**base, "type": "final", "content": said, "output": out})
    return events


@app.get("/events")
async def recent_events(limit: int = 50, ticket_id: int | None = None, since: str | None = None) -> dict:
    """Most recent agent events, newest last, from output/audit_trail.json."""
    entries = json.loads(AUDIT_TRAIL.read_text()) if AUDIT_TRAIL.exists() else []
    events = []
    for entry in entries:
        if "run_id" not in entry:
            continue
        if ticket_id is not None and entry["ticket_id"] != ticket_id:
            continue
        if since is not None and entry["ts"] <= since:
            continue
        events.extend(_events_from_entry(entry))
    return {"events": events[-limit:]}


@app.get("/payments")
async def list_payments(status: str = "pending") -> dict:
    """Payments agents have prepared. status: pending, approved, rejected, or all."""
    return await mcp_call("list_pending_payments", {"status": status})


@app.post("/payments/{pending_id}/approve")
async def approve_payment(pending_id: int, body: ApproveBody = ApproveBody()) -> dict:
    """A human clicked approve. This is the only route that changes cash."""
    result = _check(await mcp_call("approve_payment", {"pending_id": pending_id,
                                                       "approved_by": body.approved_by}))
    log_decision(result.get("ticket_id") or 0, body.approved_by, "human_approval", pending_id=pending_id, result=result)
    return result


@app.post("/payments/{pending_id}/reject")
async def reject_payment(pending_id: int, body: RejectBody) -> dict:
    result = _check(await mcp_call("reject_payment", {"pending_id": pending_id, "rejected_by": body.rejected_by,
                                                      "reason": body.reason}))
    log_decision(result.get("ticket_id") or 0, body.rejected_by, "human_rejection", pending_id=pending_id, reason=body.reason)
    return result


@app.get("/cash")
async def cash(account: str = "checking") -> dict:
    """Current balance from cash_accounts."""
    return _check(await mcp_call("get_cash", {"account": account}))


@app.post("/reset")
async def reset() -> dict:
    """Restore the working database to the original campus_customs.db. Logs are kept."""
    return await mcp_call("reset_database")
