import type { Ticket } from '../types'

const TYPE_ICON: Record<string, string> = {
  customer_order: '👕',
  rent_notice: '🏠',
  price_override: '🏷️',
}

const pretty = (s: string) => s.replaceAll('_', ' ')

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  runningId: number | null
  finished: Record<number, boolean>
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

export function TicketQueue({ tickets, selectedId, runningId, finished, onSelect, onRun }: Props) {
  return (
    <section className="panel queue">
      <header className="panel__head">
        <h2>Ticket queue</h2>
        <span className="muted">{tickets.length} tickets</span>
      </header>
      <ul className="queue__list">
        {tickets.map((t) => {
          // A plain 'open' status means the shop was reset since the run, so a saved "finished" flag is stale.
          const resolved = (finished[t.id] && t.status !== 'open') || t.state === 'resolved'
          const running = runningId === t.id
          const selected = selectedId === t.id
          return (
            <li key={t.id}>
              <button
                className={`ticket ${selected ? 'ticket--selected' : ''} ${resolved ? 'ticket--resolved' : ''}`}
                onClick={() => onSelect(t.id)}
              >
                <span className="ticket__icon">{TYPE_ICON[t.type] ?? '📄'}</span>
                <span className="ticket__body">
                  <span className="ticket__top">
                    <span className="ticket__id">#{t.id}</span>
                    <span className="ticket__type">{pretty(t.type)}</span>
                  </span>
                  <span className="ticket__subject">{t.subject}</span>
                  <span className="ticket__who">{t.requester}</span>
                  <span className="ticket__pills">
                    {running ? (
                      <span className="pill pill--live">● agents working</span>
                    ) : resolved ? (
                      <span className="pill pill--done">✓ resolved</span>
                    ) : (
                      <span className="pill">open</span>
                    )}
                    {t.status !== 'open' && t.status !== 'resolved' && (
                      <span className="pill pill--ghost">{pretty(t.status)}</span>
                    )}
                  </span>
                </span>
                {resolved && !running && <span className="stamp">Resolved</span>}
              </button>
              {selected && (
                <button className="run-btn" disabled={runningId !== null} onClick={() => onRun(t.id)}>
                  {running ? 'Agents on it…' : resolved ? 'Run the team again' : 'Start the agent team →'}
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
