import type { ConsoleLine } from '../api/useEvents'

export function Console({ lines, live }: { lines: ConsoleLine[]; live: Record<string, string> }) {
  const running = Object.entries(live)
  return (
    <section className="panel console" aria-label="Live console">
      <h2>Console</h2>
      <ol aria-live="polite">
        {lines.map((l) => (
          <li key={l.id}>
            <span className="agent">{l.agent}</span> {l.text}
          </li>
        ))}
        {running.map(([agent, text]) => (
          <li key={agent} className="running">
            <span className="agent">{agent}</span> writing… {text.length} chars
          </li>
        ))}
      </ol>
    </section>
  )
}
