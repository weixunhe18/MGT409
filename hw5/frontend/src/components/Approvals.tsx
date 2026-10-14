import { useState } from 'react'
import { money } from '../agents'
import type { PendingPayment } from '../types'

const LABEL: Record<string, string> = {
  pay_rent: 'Rent payment',
  pay_invoice: 'Vendor invoice',
  record_payment: 'Payment',
}

interface Props {
  payments: PendingPayment[]
  balance: number | null
  onApprove: (id: number) => Promise<void>
  onReject: (id: number) => Promise<void>
}

/** Payments the agents prepared. Nothing moves until a human approves here. */
export function Approvals({ payments, balance, onApprove, onReject }: Props) {
  const [busy, setBusy] = useState<number | null>(null)

  const act = async (id: number, fn: (id: number) => Promise<void>) => {
    setBusy(id)
    try {
      await fn(id)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="panel approvals">
      <header className="panel__head">
        <h2>Needs your approval</h2>
        {payments.length > 0 && <span className="badge">{payments.length}</span>}
      </header>
      {payments.length === 0 ? (
        <p className="muted small">Nothing waiting. Agents only prepare payments; they land here for you to approve.</p>
      ) : (
        payments.map((p) => {
          const after = balance === null ? null : balance - p.amount
          return (
            <div key={p.id} className="approval">
              <div className="approval__top">
                <span className="approval__kind">{LABEL[p.tool] ?? p.tool}</span>
                {p.ticket_id && <span className="muted small">ticket #{p.ticket_id}</span>}
              </div>
              <div className="approval__amount">{money(p.amount)}</div>
              <div className="approval__meta">
                Prepared by {p.prepared_by}
                {p.purpose && <> · {p.purpose}</>}
              </div>
              {after !== null && (
                <div className={`approval__after ${after < 0 ? 'neg' : ''}`}>
                  <span className="muted">Checking after</span>
                  <span>{money(after)}</span>
                </div>
              )}
              <div className="approval__actions">
                <button className="btn btn--approve" disabled={busy !== null} onClick={() => act(p.id, onApprove)}>
                  {busy === p.id ? 'Paying…' : 'Approve & pay'}
                </button>
                <button className="btn btn--ghost" disabled={busy !== null} onClick={() => act(p.id, onReject)}>
                  Reject
                </button>
              </div>
            </div>
          )
        })
      )}
    </section>
  )
}
