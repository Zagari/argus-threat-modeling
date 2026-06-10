import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { urlForId } from './CitationLinks'
import type { Subgraph } from '../types'

// Mesmas cores por camada do KnowledgeSubgraph (consistência visual entre as duas visões).
const KIND_COLOR: Record<string, string> = {
  Stride: '#64748b',
  CWE: '#3b82f6',
  CAPEC: '#f59e0b',
  ATTACK: '#ef4444',
  D3FEND: '#14b8a6',
  Control: '#10b981',
}

/**
 * Visão force-directed (estilo Neo4j Browser) do subgrafo — lê o MESMO `/knowledge/subgraph`,
 * então funciona com o LocalKG ou com o Neo4j (o bolt/credenciais ficam no servidor). Render via
 * react-force-graph-2d (MIT, Canvas). Clique num nó abre a fonte oficial.
 */
export default function KnowledgeForceGraph({ sg }: { sg: Subgraph }) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(800)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w) setWidth(Math.floor(w))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Objetos NOVOS a cada subgrafo: a lib muta source/target → não tocar nos dados originais.
  const data = useMemo(
    () => ({
      nodes: sg.nodes.map((n) => ({ id: n.id, kind: n.kind, name: n.name, url: n.url })),
      links: sg.edges.map((e) => ({ source: e.source, target: e.target, type: e.type })),
    }),
    [sg],
  )

  if (!sg.nodes.length) return <p className="muted">Sem subgrafo para esta combinação.</p>

  return (
    <div className="kg-wrap" ref={wrapRef} style={{ padding: 0, overflow: 'hidden' }}>
      <ForceGraph2D
        graphData={data as any}
        width={width}
        height={460}
        backgroundColor="#1f2330"
        nodeRelSize={5}
        nodeColor={(n: any) => KIND_COLOR[n.kind] ?? '#64748b'}
        nodeLabel={(n: any) => (n.name ? `${n.id} — ${n.name}` : n.id)}
        linkColor={() => '#475569'}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkWidth={1.2}
        cooldownTicks={120}
        onNodeClick={(n: any) => {
          const url = n.url ?? urlForId(n.id)
          if (url) window.open(url, '_blank', 'noopener,noreferrer')
        }}
        nodeCanvasObjectMode={() => 'after'}
        nodeCanvasObject={(n: any, ctx: any, scale: number) => {
          const fontSize = Math.max(2.5, 11 / scale)
          ctx.font = `${fontSize}px sans-serif`
          ctx.fillStyle = '#cbd5e1'
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          ctx.fillText(n.id, n.x, n.y + 6)
        }}
      />
    </div>
  )
}
