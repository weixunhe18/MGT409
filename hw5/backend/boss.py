"""Boss agent: routes each ticket to the right agents, chains them, and signs off on big spends."""

import json

from pydantic_ai import Agent

from backend import accounting, customer_service, facilities, inventory
from backend.common import (BOSS_LIMITS, WORKER_LIMITS, load_prompt, log_decision, mcp_call,
                            model, model_settings, run_audited)
from backend.models import ApprovalDecision, BossFollowUp, BossPlan, StepResult, TeamDeps, Ticket, TicketOutcome


MAX_STEPS = 6  # safety cap on chained steps per ticket
MAX_ALERT_FOLLOW_UPS = 2  # boss may add at most this many steps in response to alerts

WORKERS = {
    "inventory": inventory.agent,
    "accounting": accounting.agent,
    "facilities": facilities.agent,
    "customer_service": customer_service.agent,
}

router = Agent(model, name="boss", instructions=load_prompt("boss"), output_type=BossPlan,
               model_settings=model_settings)
follow_up = Agent(model, name="boss", instructions=load_prompt("boss"), output_type=BossFollowUp,
                  model_settings=model_settings)
approver = Agent(model, name="boss", instructions=load_prompt("boss"), output_type=ApprovalDecision,
                 model_settings=model_settings)


async def load_ticket(ticket_id: int) -> Ticket:
    row = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    if row.get("status") == "error":
        raise ValueError(row["message"])
    return Ticket(**row)


async def run_step(ticket: Ticket, agent_name: str, task: str, earlier: list[StepResult],
                   approval: ApprovalDecision | None = None):
    deps = TeamDeps(agent=agent_name, ticket_id=ticket.id, boss_approval=approval)
    prompt = (
        f"Ticket:\n{ticket.model_dump_json(indent=2)}\n\n"
        f"Your task from the boss:\n{task}\n"
    )
    if earlier:
        prompt += "\nWhat earlier agents did on this ticket:\n" + "\n".join(
            f"- {s.agent}: {s.report.summary}" for s in earlier
        )
    if approval:
        prompt += (f"\n\nThe boss APPROVED spending up to {approval.max_amount:.2f}: {approval.reasoning}. "
                   "Go ahead and make the payment now.")
    result = await run_audited(WORKERS[agent_name], prompt, ticket_id=ticket.id, role=agent_name,
                               limits=WORKER_LIMITS, deps=deps)
    return result.output, deps.tool_calls


async def handle_ticket(ticket_id: int) -> TicketOutcome:
    ticket = await load_ticket(ticket_id)

    plan = (await run_audited(router, f"New ticket:\n{ticket.model_dump_json(indent=2)}",
                              ticket_id=ticket.id, role="boss", limits=BOSS_LIMITS)).output
    log_decision(ticket.id, "boss", "route", reasoning=plan.reasoning,
                 chain=[s.agent for s in plan.steps], steps=[s.model_dump() for s in plan.steps])

    steps: list[StepResult] = []
    queue = list(plan.steps)
    alert_follow_ups = 0
    while queue and len(steps) < MAX_STEPS:
        step = queue.pop(0)
        report, calls = await run_step(ticket, step.agent, step.task, steps)
        approval = None
        request = None

        if report.status == "needs_boss_approval":
            request = report.approval_request or next(
                ({"tool": c["tool"], "amount": c["result"]["amount"], "limit": c["result"]["limit"]}
                 for c in calls if c["result"].get("status") == "needs_boss_approval"), None)
        if report.status == "needs_boss_approval" and request is not None:
            approval = (await run_audited(approver,
                "An agent needs your sign-off on a payment over its limit.\n"
                f"Agent: {step.agent}\nTicket:\n{ticket.model_dump_json(indent=2)}\n"
                f"Request: {json.dumps(request if isinstance(request, dict) else request.model_dump())}\n"
                f"Agent's report: {report.model_dump_json()}",
                ticket_id=ticket.id, role="boss", limits=BOSS_LIMITS)).output
            log_decision(ticket.id, "boss", "approval", agent=step.agent, request=request,
                         **approval.model_dump())
            if approval.approved:
                report, calls = await run_step(ticket, step.agent, step.task, steps, approval)

        log_decision(ticket.id, step.agent, "report", status=report.status, summary=report.summary,
                     customer_message=report.customer_message, follow_up=report.follow_up)
        result = StepResult(agent=step.agent, task=step.task, report=report, approval=approval)

        if report.boss_alert and alert_follow_ups >= MAX_ALERT_FOLLOW_UPS:
            log_decision(ticket.id, "boss", "alert_ignored", reason="alert follow-up cap reached",
                         **report.boss_alert.model_dump())
        elif report.boss_alert:
            log_decision(ticket.id, step.agent, "alert_boss", **report.boss_alert.model_dump())
            decision = (await run_audited(follow_up,
                f"{step.agent} raised an alert while working this ticket.\n"
                f"Ticket:\n{ticket.model_dump_json(indent=2)}\n"
                f"Alert: {report.boss_alert.model_dump_json()}\n"
                f"Agent's report: {report.summary}\n"
                f"Steps still planned: {[s.agent for s in queue]}",
                ticket_id=ticket.id, role="boss", limits=BOSS_LIMITS)).output
            log_decision(ticket.id, "boss", "alert_response", reasoning=decision.reasoning,
                         next_step=decision.next_step.model_dump() if decision.next_step else None)
            if decision.next_step and decision.next_step.agent == step.agent:
                # Sending an agent back to the problem it just raised wastes tokens; a human must step in.
                log_decision(ticket.id, "boss", "alert_ignored", reason="same agent re-sent its own alert",
                             next_step=decision.next_step.model_dump())
            elif decision.next_step:
                queue.insert(0, decision.next_step)
                alert_follow_ups += 1
            result.boss_follow_up = decision

        steps.append(result)

    return TicketOutcome(ticket_id=ticket.id, plan=plan, steps=steps)


async def open_ticket_ids() -> list[int]:
    return [t["id"] for t in (await mcp_call("list_open_tickets"))["tickets"]]
