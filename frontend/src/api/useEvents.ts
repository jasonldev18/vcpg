import { useEffect, useState } from 'react'
import { API_BASE } from './client'

export interface ConsoleLine {
  id: number
  agent: string
  text: string
}

export interface Events {
  lines: ConsoleLine[]
  live: Record<string, string> // text streamed so far by each agent that is running now
  version: number // bumps when a step changes in the background, so screens refetch it
}

const KEEP = 200

// One EventSource per open project; the browser resends Last-Event-ID when it reconnects.
export function useEvents(projectId: number | null): Events {
  const [events, setEvents] = useState<Events>({ lines: [], live: {}, version: 0 })

  useEffect(() => {
    if (projectId === null) return
    const source = new EventSource(`${API_BASE}/api/events?project_id=${projectId}`)
    const on = (
      type: string,
      apply: (e: Events, data: Record<string, unknown>, id: number) => Events,
    ) =>
      source.addEventListener(type, (msg: MessageEvent<string>) =>
        setEvents((e) => apply(e, JSON.parse(msg.data), Number(msg.lastEventId))),
      )
    const log = (e: Events, line: ConsoleLine): ConsoleLine[] => [...e.lines, line].slice(-KEEP)

    on('agent_started', (e, d, id) => ({
      ...e,
      live: { ...e.live, [d.agent as string]: '' },
      lines: log(e, { id, agent: d.agent as string, text: 'started' }),
    }))
    on('agent_text', (e, d) => {
      const agent = d.agent as string
      return { ...e, live: { ...e.live, [agent]: (e.live[agent] ?? '') + (d.text as string) } }
    })
    on('agent_finished', (e, d, id) => {
      const { [d.agent as string]: done, ...live } = e.live
      const summary = d.ok ? `finished (${done?.length ?? 0} chars)` : 'failed'
      return { ...e, live, lines: log(e, { id, agent: d.agent as string, text: summary }) }
    })
    on('tool_use', (e, d, id) => ({
      ...e,
      lines: log(e, {
        id,
        agent: d.agent as string,
        text: d.denied ? `denied: ${d.summary as string}` : (d.summary as string),
      }),
    }))
    on('build_failed', (e, d, id) => ({
      ...e,
      version: e.version + 1,
      lines: log(e, { id, agent: 'builder', text: `failed: ${d.error as string}` }),
    }))
    on('project_stage', (e, d, id) => ({
      ...e,
      version: e.version + 1,
      lines: log(e, { id, agent: 'orchestrator', text: `project → ${d.stage as string}` }),
    }))
    on('build_stopped', (e, _d, id) => ({
      ...e,
      version: e.version + 1,
      lines: log(e, { id, agent: 'builder', text: 'stopped by you' }),
    }))
    on('state_changed', (e, d, id) => ({
      ...e,
      version: e.version + 1,
      lines: log(e, { id, agent: 'orchestrator', text: `step ${d.step_id} → ${d.state}` }),
    }))
    on('gate_update', (e, d, id) => ({
      ...e,
      lines: log(e, { id, agent: 'grader', text: `${d.covered} of ${d.total} points covered` }),
    }))
    return () => source.close()
  }, [projectId])

  return events
}
