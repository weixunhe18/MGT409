import type { AgentEvent, AgentId } from './types'

export const AGENTS: { id: AgentId; name: string; role: string; glyph: string; color: string }[] = [
  { id: 'boss', name: 'The Boss', role: 'Routes tickets · signs off', glyph: '★', color: '#00c805' },
  { id: 'inventory', name: 'Inventory', role: 'Stock · reorders', glyph: '▦', color: '#5ac8fa' },
  { id: 'customer_service', name: 'Customer Service', role: 'Offers · replies (Stark mode)', glyph: '✦', color: '#ff6fb5' },
  { id: 'facilities', name: 'Facilities', role: 'Rent · utilities · repairs', glyph: '⌂', color: '#ffc24b' },
  { id: 'accounting', name: 'Accounting', role: 'Books · invoices', glyph: '$', color: '#a78bfa' },
]

export const agentMeta = (id: string) => AGENTS.find((a) => a.id === id) ?? AGENTS[0]

const TOOL_VERBS: Record<string, string> = {
  get_ticket: 'Reading the ticket',
  get_inventory: 'Checking stock on the shelves',
  get_books: 'Opening the books',
  fulfill_customer_order: 'Filling the order',
  reorder_stock: 'Ordering more from the vendor',
  receive_stock: 'Receiving a delivery',
  negotiate_discount: 'Working out a discount',
  pay_rent: 'Preparing the rent payment',
  pay_invoice: 'Preparing an invoice payment',
  record_payment: 'Preparing a payment',
  record_invoice: 'Recording a vendor bill',
  record_income: 'Recording money in',
  check_spend_limit: 'Checking the spend limit',
  update_ticket_status: 'Updating the ticket',
}

export const toolVerb = (tool?: string) => (tool ? TOOL_VERBS[tool] ?? tool : '')

export const money = (n: unknown) =>
  typeof n === 'number' ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : ''

/** One plain-English line for a feed event. */
export function describe(e: AgentEvent): string {
  if (e.type === 'tool_call') return `${toolVerb(e.tool)}…`
  if (e.type === 'final') return typeof e.content === 'string' ? e.content : 'Finished.'
  if (e.type === 'said') return String(e.content ?? '')
  // tool_result
  const r = (e.content ?? {}) as Record<string, unknown>
  switch (e.tool) {
    case 'fulfill_customer_order':
      return r.status === 'fulfilled'
        ? `Filled from ${r.location}; ${r.remaining_stock} left.`
        : `Backordered: ${r.shortfall} short. ${r.message ?? ''}. ETA ${r.expected_date}.`
    case 'reorder_stock':
      return `${r.message}. ETA ${r.expected_date}.`
    case 'negotiate_discount':
      return `Offer: ${r.discount_pct}% off, ${money(r.unit_price)}/unit, ${money(r.order_total)} total. ${r.in_stock} in stock.`
    case 'check_spend_limit':
      return `${money(r.amount)} against a ${money(r.limit)} limit: ${r.needs_boss_approval ? 'needs the boss' : 'within limit'}${r.boss_approved ? ' (boss approved)' : ''}.`
    case 'pay_rent':
    case 'pay_invoice':
    case 'record_payment':
      return r.status === 'prepared' || r.status === 'already_pending'
        ? `Prepared ${money(r.amount)}. Waiting for a human to approve.`
        : r.status === 'needs_boss_approval'
          ? 'Over the limit, so asking the boss.'
          : String(r.message ?? r.status ?? 'Done')
    case 'get_inventory': {
      const out = (r.out_of_stock as string[] | undefined) ?? []
      return out.length ? `Out of stock: ${out.join(', ')}.` : 'Stock looks fine.'
    }
    case 'get_books': {
      const cash = (r.cash_accounts as { balance: number }[] | undefined)?.[0]
      return cash ? `Checking is at ${money(cash.balance)}.` : 'Books opened.'
    }
    case 'update_ticket_status':
      return `Ticket marked ${String(r.status).replaceAll('_', ' ')}.`
    default:
      return typeof r.message === 'string' ? r.message : 'Done.'
  }
}
