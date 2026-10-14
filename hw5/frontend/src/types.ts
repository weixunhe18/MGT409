export type AgentId = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  status: string
  state: 'open' | 'resolved'
}

export interface AgentEvent {
  ts: string
  ticket_id: number
  agent: AgentId
  run_id: string
  step: number
  type: 'said' | 'tool_call' | 'tool_result' | 'final'
  tool?: string
  args?: Record<string, unknown>
  content?: unknown
}

export interface AgentReport {
  status: 'done' | 'needs_boss_approval' | 'escalate' | 'blocked'
  summary: string
  actions: string[]
  customer_message: string | null
  follow_up: string | null
}

export interface StepResult {
  agent: Exclude<AgentId, 'boss'>
  task: string
  report: AgentReport
  approval: { approved: boolean; max_amount: number; reasoning: string } | null
  boss_follow_up: { reasoning: string } | null
}

export interface TicketOutcome {
  ticket_id: number
  plan: { reasoning: string; steps: { agent: AgentId; task: string }[] }
  steps: StepResult[]
}

export interface PendingPayment {
  id: number
  tool: string
  args: Record<string, unknown>
  amount: number
  purpose: string | null
  prepared_by: string
  ticket_id: number | null
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  decided_by: string | null
}

export interface Cash {
  name: string
  balance: number
  date: string
}
