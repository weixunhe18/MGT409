"""Run the agent team on tickets.

    python -m backend.run_ticket 101 102 103
    python -m backend.run_ticket --open      # every open ticket, from list_open_tickets
"""

import asyncio
import sys

from backend.boss import handle_ticket, open_ticket_ids


async def main(args: list[str]) -> None:
    ticket_ids = await open_ticket_ids() if args == ["--open"] else [int(a) for a in args]
    for ticket_id in ticket_ids:
        outcome = await handle_ticket(ticket_id)
        print(f"\n=== Ticket {ticket_id} ===")
        print(f"Boss: {outcome.plan.reasoning}")
        for step in outcome.steps:
            print(f"\n[{step.agent}] {step.report.status}: {step.report.summary}")
            if step.approval:
                verdict = "approved" if step.approval.approved else "refused"
                print(f"  boss {verdict}: {step.approval.reasoning}")
            if step.boss_follow_up:
                print(f"  boss on alert: {step.boss_follow_up.reasoning}")
            if step.report.customer_message:
                print(f"  to customer: {step.report.customer_message}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
