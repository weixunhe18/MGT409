"""Data types shared by the Campus Customs agent team."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


AgentName = Literal["inventory", "accounting", "facilities", "customer_service"]


class Ticket(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str


class Delegation(BaseModel):
    """One step in the boss's plan: which agent does what."""

    agent: AgentName
    task: str = Field(description="Specific instructions for this agent, including ids and amounts")


class BossPlan(BaseModel):
    """The boss's routing decision for a ticket. Steps run in order."""

    reasoning: str = Field(description="Why these agents, in this order")
    steps: list[Delegation] = Field(min_length=1)


class ApprovalRequest(BaseModel):
    """What a worker asks the boss to sign off on when a payment is over its limit."""

    tool: str
    amount: float
    limit: float
    purpose: str


class ApprovalDecision(BaseModel):
    """The boss's sign-off (or refusal) on an over-limit payment."""

    approved: bool
    max_amount: float = Field(description="Largest amount approved; 0 if refused")
    reasoning: str


class BossAlert(BaseModel):
    """A problem a worker found that needs the boss to bring in another agent."""

    issue: str = Field(description="What's wrong, with numbers (e.g. 12 short of a 20-unit order)")
    suggested_agent: AgentName | None = None
    suggested_task: str | None = None


class BossFollowUp(BaseModel):
    """The boss's response to an alert: add another step, or not."""

    reasoning: str
    next_step: Delegation | None = Field(default=None, description="Step to run next, or null if none needed")


class AgentReport(BaseModel):
    """What a worker agent hands back to the boss."""

    status: Literal["done", "needs_boss_approval", "escalate", "blocked"] = Field(
        description="needs_boss_approval is ONLY for a payment over your spend limit; "
                    "use boss_alert for other problems the boss should act on"
    )
    summary: str = Field(description="What you did and what changed, with numbers")
    actions: list[str] = Field(default_factory=list, description="Each tool call you made and its result")
    approval_request: ApprovalRequest | None = None
    customer_message: str | None = Field(
        default=None, description="Reply to send the customer, if this ticket needs one"
    )
    follow_up: str | None = Field(default=None, description="Anything another agent or a human must do next")
    boss_alert: BossAlert | None = Field(
        default=None, description="Set when the boss must act, e.g. stock is short for a pending order"
    )


class StepResult(BaseModel):
    agent: AgentName
    task: str
    report: AgentReport
    approval: ApprovalDecision | None = None
    boss_follow_up: BossFollowUp | None = None


class TicketOutcome(BaseModel):
    ticket_id: int
    plan: BossPlan
    steps: list[StepResult]


@dataclass
class TeamDeps:
    """Run-time context passed to every worker agent."""

    agent: AgentName
    ticket_id: int
    boss_approval: ApprovalDecision | None = None
    tool_calls: list[dict] = field(default_factory=list)
