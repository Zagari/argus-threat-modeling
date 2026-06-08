import type { Subgraph, SubgraphNode } from '../types'
import { urlForId } from './CitationLinks'

const TIERS = ['Stride', 'CWE', 'CAPEC', 'Control'] as const
const TIER_LABEL: Record<string, string> = { Stride: 'STRIDE', CWE: 'CWE', CAPEC: 'CAPEC', Control: 'Controles (ASVS)' }
const KIND_COLOR: Record<string, string> = {
  Stride: '#64748b',
  CWE: '#3b82f6',
  CAPEC: '#f59e0b',
  Control: '#10b981',
}

const NW = 178
const NH = 40
const COLW = 220
const ROWH = 52
const PAD = 14
const HEADER = 22

function trunc(s: string, n = 24): string {
  return s.length <= n ? s : s.slice(0, n - 1) + '…'
}

/** Diagrama node-link em camadas do subgrafo de conhecimento (nós clicáveis → fonte). */
export default function KnowledgeSubgraph({ sg }: { sg: Subgraph }) {
  const byTier: Record<string, SubgraphNode[]> = {}
  for (const n of sg.nodes) (byTier[n.kind] ??= []).push(n)

  const pos = new Map<string, { x: number; y: number }>()
  TIERS.forEach((kind, ti) => {
    ;(byTier[kind] ?? []).forEach((n, i) => pos.set(n.id, { x: ti * COLW + PAD, y: i * ROWH + PAD + HEADER }))
  })

  const maxRows = Math.max(1, ...TIERS.map((k) => (byTier[k] ?? []).length))
  const W = TIERS.length * COLW
  const H = maxRows * ROWH + PAD * 2 + HEADER

  if (!sg.nodes.length) return <p className="muted">Sem subgrafo para esta combinação.</p>

  return (
    <div className="kg-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="xMinYMin meet" style={{ minWidth: W * 0.7 }}>
        <defs>
          <marker id="kg-arr" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L6,3 L0,6 Z" fill="#475569" />
          </marker>
        </defs>

        {/* títulos das camadas */}
        {TIERS.map((kind, ti) =>
          (byTier[kind] ?? []).length ? (
            <text key={kind} x={ti * COLW + PAD} y={14} fontSize={11} fill={KIND_COLOR[kind]} fontWeight={700}>
              {TIER_LABEL[kind]}
            </text>
          ) : null,
        )}

        {/* arestas */}
        {sg.edges.map((e, i) => {
          const a = pos.get(e.source)
          const b = pos.get(e.target)
          if (!a || !b) return null
          return (
            <line
              key={i}
              x1={a.x + NW}
              y1={a.y + NH / 2}
              x2={b.x}
              y2={b.y + NH / 2}
              stroke="#475569"
              strokeWidth={1.4}
              markerEnd="url(#kg-arr)"
              opacity={0.7}
            />
          )
        })}

        {/* nós */}
        {sg.nodes.map((n) => {
          const p = pos.get(n.id)
          if (!p) return null
          const color = KIND_COLOR[n.kind] ?? '#64748b'
          const url = n.url ?? urlForId(n.id)
          const box = (
            <g>
              <rect x={p.x} y={p.y} width={NW} height={NH} rx={6} fill={`${color}1f`} stroke={color} strokeWidth={1.5} />
              <text x={p.x + 8} y={p.y + 16} fontSize={11} fontWeight={700} fill={color}>
                {n.id}
              </text>
              <text x={p.x + 8} y={p.y + 30} fontSize={10} fill="#cbd5e1">
                {trunc(n.name)}
              </text>
            </g>
          )
          return url ? (
            <a key={n.id} href={url} target="_blank" rel="noreferrer">
              {box}
            </a>
          ) : (
            <g key={n.id}>{box}</g>
          )
        })}
      </svg>
    </div>
  )
}
