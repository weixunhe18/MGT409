import { useEffect, useRef } from 'react'
import { agentMeta, describe, toolVerb } from '../agents'
import type { AgentEvent } from '../types'

const time = (ts: string) => ts.slice(11, 19)

/** Live play-by-play of the run: what each agent said and which tools it used. */
export function EventFeed({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [events.length])

  // Tool calls and their results arrive as separate events; show the result line under the call.
  const rows = events.filter((e) => e.type !== 'tool_call')

  return (
    <div className="feed">
      {rows.length === 0 && (
        <p className="feed__empty">{running ? 'The boss is reading the ticket…' : 'No run yet. Pick a ticket and start the team.'}</p>
      )}
      {rows.map((e, i) => {
        const a = agentMeta(e.agent)
        return (
          <div key={`${e.run_id}-${e.step}-${i}`} className={`feed__row feed__row--${e.type}`}>
            <span className="feed__time">{time(e.ts)}</span>
            <span className="feed__dot" style={{ background: a.color }} />
            <div className="feed__text">
              <span className="feed__agent" style={{ color: a.color }}>{a.name}</span>
              {e.type === 'tool_result' && <span className="feed__tool">{toolVerb(e.tool)}</span>}
              {e.type === 'final' && <span className="feed__tool feed__tool--final">reported</span>}
              <p>{describe(e)}</p>
            </div>
          </div>
        )
      })}
      {running && (
        <div className="feed__row feed__row--pending">
          <span className="feed__time" />
          <span className="feed__dot feed__dot--pulse" />
          <span className="typing"><i /><i /><i /></span>
        </div>
      )}
      <div ref={end} />
    </div>
  )
}
