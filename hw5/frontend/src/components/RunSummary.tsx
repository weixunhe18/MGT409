import { agentMeta } from '../agents'
import type { TicketOutcome } from '../types'

const STATUS: Record<string, string> = {
  done: 'Done',
  needs_boss_approval: 'Needed the boss',
  escalate: 'Escalated',
  blocked: 'Blocked',
}

/** Short summary of what each agent did on the selected ticket. */
export function RunSummary({ outcome, ticketId }: { outcome: TicketOutcome | undefined; ticketId: number | null }) {
  return (
    <section className="panel summary">
      <header className="panel__head">
        <h2>What each agent did</h2>
        {ticketId && <span className="muted">#{ticketId}</span>}
      </header>
      {!outcome ? (
        <p className="muted small">Run the team on this ticket to see a summary.</p>
      ) : (
        <>
          <div className="sum sum--boss" style={{ '--agent': agentMeta('boss').color } as React.CSSProperties}>
            <div className="sum__who">
              <span className="sum__glyph">{agentMeta('boss').glyph}</span> The Boss
              <span className="sum__chain">{outcome.plan.steps.map((s) => agentMeta(s.agent).name).join(' → ')}</span>
            </div>
            <p>{outcome.plan.reasoning}</p>
          </div>
          {outcome.steps.map((s, i) => {
            const a = agentMeta(s.agent)
            return (
              <div key={i} className="sum" style={{ '--agent': a.color } as React.CSSProperties}>
                <div className="sum__who">
                  <span className="sum__glyph">{a.glyph}</span> {a.name}
                  <span className={`sum__status sum__status--${s.report.status}`}>{STATUS[s.report.status]}</span>
                </div>
                <p>{s.report.summary}</p>
                {s.approval && (
                  <p className="sum__note">
                    Boss {s.approval.approved ? 'signed off' : 'refused'}: {s.approval.reasoning}
                  </p>
                )}
                {s.boss_follow_up && <p className="sum__note">Boss on the alert: {s.boss_follow_up.reasoning}</p>}
                {s.report.customer_message && (
                  <blockquote className="sum__quote">“{s.report.customer_message}”</blockquote>
                )}
              </div>
            )
          })}
        </>
      )}
    </section>
  )
}
