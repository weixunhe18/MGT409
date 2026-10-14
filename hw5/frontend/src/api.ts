import type { AgentEvent, Cash, PendingPayment, Ticket, TicketOutcome } from './types'

// Problem 7 FastAPI server (start it from backend/ with: uvicorn main:app --reload --port 8000)
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  tickets: () => call<{ tickets: Ticket[] }>('/tickets').then((r) => r.tickets),
  runTicket: (id: number) => call<TicketOutcome>(`/tickets/${id}/run`, { method: 'POST' }),
  events: (ticketId: number, limit = 300) =>
    call<{ events: AgentEvent[] }>(`/events?ticket_id=${ticketId}&limit=${limit}`).then((r) => r.events),
  payments: (status = 'pending') =>
    call<{ payments: PendingPayment[] }>(`/payments?status=${status}`).then((r) => r.payments),
  approve: (id: number, approvedBy: string) =>
    call(`/payments/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved_by: approvedBy }) }),
  reject: (id: number, reason: string) =>
    call(`/payments/${id}/reject`, { method: 'POST', body: JSON.stringify({ rejected_by: 'desk', reason }) }),
  cash: () => call<Cash>('/cash'),
  reset: () => call('/reset', { method: 'POST' }),
}
