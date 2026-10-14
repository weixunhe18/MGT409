import { AGENTS, describe } from '../agents'
import type { AgentEvent } from '../types'

interface Props {
  events: AgentEvent[]
  running: boolean
}

/** One desk per agent. The agent currently working glows, with a speech bubble of what it's doing. */
export function AgentFloor({ events, running }: Props) {
  const latest = events[events.length - 1]
  const activeId = running ? latest?.agent ?? 'boss' : null
  const involved = new Set(events.map((e) => e.agent))

  return (
    <div className="floor">
      {AGENTS.map((a) => {
        const mine = events.filter((e) => e.agent === a.id)
        const last = mine[mine.length - 1]
        const active = activeId === a.id
        const toolCount = mine.filter((e) => e.type === 'tool_call').length
        return (
          <div
            key={a.id}
            className={`seat ${active ? 'seat--active' : ''} ${involved.has(a.id) ? 'seat--involved' : 'seat--idle'}`}
            style={{ '--agent': a.color } as React.CSSProperties}
          >
            <div className="seat__avatar">{a.glyph}</div>
            <div className="seat__name">{a.name}</div>
            <div className="seat__role">{a.role}</div>
            <div className="seat__bubble">
              {active && !last ? (
                <span className="typing"><i /><i /><i /></span>
              ) : last ? (
                <span className="seat__line">{describe(last)}</span>
              ) : (
                <span className="muted">{running ? 'Waiting for the boss…' : 'Idle'}</span>
              )}
              {active && last && <span className="typing typing--inline"><i /><i /><i /></span>}
            </div>
            {toolCount > 0 && <div className="seat__count">{toolCount} tool call{toolCount > 1 ? 's' : ''}</div>}
          </div>
        )
      })}
    </div>
  )
}
