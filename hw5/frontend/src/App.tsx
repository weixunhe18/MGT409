import { useCallback, useEffect, useRef, useState } from 'react'
import { api, API_URL } from './api'
import { Approvals } from './components/Approvals'
import { AgentFloor } from './components/AgentFloor'
import { CashCard } from './components/CashCard'
import { EventFeed } from './components/EventFeed'
import { RunSummary } from './components/RunSummary'
import { TicketQueue } from './components/TicketQueue'
import type { AgentEvent, Cash, PendingPayment, Ticket, TicketOutcome } from './types'
import './App.css'

// Run results survive a page reload; Reset clears them.
const STORE = 'campus-desk'
interface Saved {
  outcomes: Record<number, TicketOutcome>
  finished: Record<number, boolean>
  runIds: Record<number, string[]>
}
const load = (): Saved => {
  try {
    return { outcomes: {}, finished: {}, runIds: {}, ...JSON.parse(localStorage.getItem(STORE) ?? '{}') }
  } catch {
    return { outcomes: {}, finished: {}, runIds: {} }
  }
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [payments, setPayments] = useState<PendingPayment[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [runningId, setRunningId] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [saved, setSaved] = useState<Saved>(load)
  const [error, setError] = useState<string | null>(null)
  const [online, setOnline] = useState(true)
  const seenRuns = useRef<Set<string>>(new Set())

  useEffect(() => localStorage.setItem(STORE, JSON.stringify(saved)), [saved])

  const refresh = useCallback(async () => {
    try {
      const [t, c, p] = await Promise.all([api.tickets(), api.cash(), api.payments()])
      setTickets(t)
      setCash(c)
      setPayments(p)
      setOnline(true)
      setSelectedId((id) => id ?? t[0]?.id ?? null)
    } catch {
      setOnline(false)
    }
  }, [])

  // Board refresh: tickets, cash, and approvals every few seconds.
  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [refresh])

  // Feed for the selected ticket: its most recent run (or the live one).
  useEffect(() => {
    if (selectedId === null) return
    let stop = false
    const pull = async () => {
      try {
        const all = await api.events(selectedId)
        if (stop) return
        if (runningId === selectedId) {
          setEvents(all.filter((e) => !seenRuns.current.has(e.run_id)))
        } else {
          const ids = new Set(saved.runIds[selectedId] ?? [])
          setEvents(all.filter((e) => ids.has(e.run_id)))
        }
      } catch {
        /* the offline banner covers this */
      }
    }
    pull()
    if (runningId !== selectedId) return () => { stop = true }
    const id = setInterval(pull, 1200)
    return () => {
      stop = true
      clearInterval(id)
    }
  }, [selectedId, runningId, saved.runIds])

  const runTicket = async (id: number) => {
    setError(null)
    setSelectedId(id)
    try {
      const before = await api.events(id, 5000)
      seenRuns.current = new Set(before.map((e) => e.run_id))
      setEvents([])
      setRunningId(id)
      const outcome = await api.runTicket(id)
      const after = await api.events(id, 5000)
      const fresh = [...new Set(after.map((e) => e.run_id))].filter((r) => !seenRuns.current.has(r))
      setSaved((s) => ({
        outcomes: { ...s.outcomes, [id]: outcome },
        finished: { ...s.finished, [id]: true },
        runIds: { ...s.runIds, [id]: fresh },
      }))
    } catch (e) {
      setError(`Run failed: ${(e as Error).message}`)
    } finally {
      setRunningId(null)
      refresh()
    }
  }

  const approve = async (pid: number) => {
    try {
      await api.approve(pid, 'desk (human)')
    } catch (e) {
      setError(`Approve failed: ${(e as Error).message}`)
    }
    await refresh()
  }

  const reject = async (pid: number) => {
    const reason = window.prompt('Why reject this payment?')
    if (!reason) return
    try {
      await api.reject(pid, reason)
    } catch (e) {
      setError(`Reject failed: ${(e as Error).message}`)
    }
    await refresh()
  }

  const reset = async () => {
    if (!window.confirm('Reset the shop database to the original values? Run results on this board are cleared too.')) return
    await api.reset()
    setSaved({ outcomes: {}, finished: {}, runIds: {} })
    setEvents([])
    await refresh()
  }

  const selected = tickets.find((t) => t.id === selectedId)
  const running = runningId !== null && runningId === selectedId

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark">CC</span>
          <div>
            <h1>Campus Customs</h1>
            <span className="brand__sub">Front desk · Chapel Street · shop date {cash?.date ?? '…'}</span>
          </div>
        </div>
        <div className="topbar__right">
          <CashCard cash={cash} />
          <button className="btn btn--ghost btn--small" onClick={reset} disabled={runningId !== null}>
            ↺ Reset shop
          </button>
        </div>
      </header>

      {!online && (
        <div className="banner">
          Can't reach the desk API at {API_URL}. Start it from <code>backend/</code> with{' '}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}
      {error && (
        <div className="banner banner--error" onClick={() => setError(null)}>
          {error} <span className="muted">(click to dismiss)</span>
        </div>
      )}

      <main className="grid">
        <TicketQueue
          tickets={tickets}
          selectedId={selectedId}
          runningId={runningId}
          finished={saved.finished}
          onSelect={setSelectedId}
          onRun={runTicket}
        />

        <section className="panel stage">
          <header className="panel__head">
            <h2>
              Agent floor
              {selected && <span className="stage__ticket"> · #{selected.id} {selected.subject}</span>}
            </h2>
            {running ? <span className="pill pill--live">● live</span> : <span className="muted">last run</span>}
          </header>
          <AgentFloor events={events} running={running} />
          <h3 className="stage__sub">Play-by-play</h3>
          <EventFeed events={events} running={running} />
        </section>

        <div className="side">
          <Approvals payments={payments} balance={cash?.balance ?? null} onApprove={approve} onReject={reject} />
          <RunSummary outcome={selectedId ? saved.outcomes[selectedId] : undefined} ticketId={selectedId} />
        </div>
      </main>
    </div>
  )
}
