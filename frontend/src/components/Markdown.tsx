import { useEffect, useId, useState } from 'react'
import ReactMarkdown from 'react-markdown'

let mermaidReady: Promise<typeof import('mermaid').default> | undefined

function loadMermaid() {
  mermaidReady ??= import('mermaid').then(({ default: mermaid }) => {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'strict' })
    return mermaid
  })
  return mermaidReady
}

function Mermaid({ source }: { source: string }) {
  const id = `m${useId().replace(/:/g, '')}`
  const [svg, setSvg] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    loadMermaid()
      .then((m) => m.render(id, source))
      .then((r) => alive && setSvg(r.svg))
      .catch(() => alive && setSvg(null))
    return () => {
      alive = false
    }
  }, [id, source])

  // Unparseable diagrams (common while text is still streaming) fall back to the source.
  if (svg === null) return <pre className="mermaid-source">{source}</pre>
  return (
    <div
      className="mermaid"
      role="img"
      aria-label="Diagram"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        components={{
          code({ className, children }) {
            const source = String(children)
            if (className === 'language-mermaid') return <Mermaid source={source} />
            return <code className={className}>{children}</code>
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
