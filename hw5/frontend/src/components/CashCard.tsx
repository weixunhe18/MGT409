import { useEffect, useRef, useState } from 'react'
import { money } from '../agents'
import type { Cash } from '../types'

/** Checking balance, portfolio-style: big number, change line, and a sparkline of this session's balances. */
export function CashCard({ cash }: { cash: Cash | null }) {
  const [shown, setShown] = useState<number | null>(null)
  const [history, setHistory] = useState<number[]>([])
  const prev = useRef<number | null>(null)

  useEffect(() => {
    if (!cash) return
    const from = prev.current
    const to = cash.balance
    if (from === to) return
    prev.current = to
    setHistory((h) => (h.length === 0 ? [to, to] : [...h, to]).slice(-30))
    if (from === null) {
      setShown(to)
      return
    }
    // Count from the old balance to the new one.
    const start = performance.now()
    let frame = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 900)
      setShown(from + (to - from) * (1 - Math.pow(1 - p, 3)))
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(frame)
      setShown(to)
    }
  }, [cash])

  const first = history[0]
  const last = history[history.length - 1]
  const lastChange = history.length > 1 ? last - history[history.length - 2] : 0
  const down = lastChange < 0
  const color = down ? 'var(--red)' : 'var(--green)'

  return (
    <div className="cash">
      <Sparkline values={history} color={color} />
      <div className="cash__text">
        <span className="cash__label">Checking</span>
        <span className="cash__value">{shown === null ? '—' : money(shown)}</span>
        <span className={`cash__change ${down ? 'neg' : ''}`}>
          {history.length > 2 && lastChange !== 0 ? (
            <>
              {down ? '−' : '+'}
              {money(Math.abs(lastChange))} ({down ? '−' : '+'}
              {Math.abs((lastChange / (last - lastChange)) * 100).toFixed(2)}%){' '}
              <span className="cash__date">last change</span>
            </>
          ) : (
            <span className="cash__date">
              {first !== undefined && last !== first ? `${money(last - first)} today` : `as of ${cash?.date ?? '…'}`}
            </span>
          )}
        </span>
      </div>
    </div>
  )
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const w = 220
  const h = 56
  if (values.length < 2) return <svg className="spark" viewBox={`0 0 ${w} ${h}`} />
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = hi - lo || 1
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - 6 - ((v - lo) / span) * (h - 12)])
  const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const [lx, ly] = pts[pts.length - 1]
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} aria-label="Checking balance this session">
      <path d={d} style={{ stroke: color }} />
      <circle cx={lx} cy={ly} r={4} fill={color} />
    </svg>
  )
}
