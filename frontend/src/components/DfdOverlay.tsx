import { useState } from 'react'
import type { Component, Edge, ElementType } from '../types'

// Cor por tipo DFD (mesma leitura visual do pipeline).
const COLORS: Record<ElementType, string> = {
  Process: '#3b82f6',
  DataStore: '#f59e0b',
  ExternalEntity: '#10b981',
  TrustBoundary: '#a855f7',
  DataFlow: '#64748b',
}

function center(b: number[]): [number, number] {
  return [b[0] + b[2] / 2, b[1] + b[3] / 2]
}

/** Desenha o DFD (componentes + fronteiras + fluxos) sobre a imagem do diagrama. */
export default function DfdOverlay({
  src,
  components,
  edges,
}: {
  src: string
  components: Component[]
  edges: Edge[]
}) {
  const [dim, setDim] = useState<{ w: number; h: number } | null>(null)
  const byId = new Map(components.map((c) => [c.id, c]))
  const boundaries = components.filter((c) => c.element_type === 'TrustBoundary')
  const nodes = components.filter((c) => c.element_type !== 'TrustBoundary')

  const W = dim?.w ?? 1000
  const H = dim?.h ?? 700
  const sw = Math.max(2, Math.round(W / 380)) // espessura de traço (px naturais)
  const fs = Math.max(11, Math.round(W / 62)) // fonte

  return (
    <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', lineHeight: 0 }}>
      <img
        src={src}
        alt="diagrama"
        style={{ display: 'block', maxWidth: '100%' }}
        onLoad={(e) => setDim({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
      />
      {dim && (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="xMidYMid meet"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        >
          <defs>
            {['#dc2626', '#94a3b8'].map((c, i) => (
              <marker
                key={i}
                id={`arr-${i}`}
                markerWidth="7"
                markerHeight="7"
                refX="5.5"
                refY="3"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L6,3 L0,6 Z" fill={c} />
              </marker>
            ))}
          </defs>

          {/* fronteiras de confiança (tracejado roxo) */}
          {boundaries.map((b) =>
            b.bbox ? (
              <g key={b.id}>
                <rect
                  x={b.bbox[0] * W}
                  y={b.bbox[1] * H}
                  width={b.bbox[2] * W}
                  height={b.bbox[3] * H}
                  fill="none"
                  stroke={COLORS.TrustBoundary}
                  strokeWidth={sw}
                  strokeDasharray={`${sw * 3} ${sw * 2}`}
                  rx={4}
                />
                <text x={b.bbox[0] * W + 3} y={b.bbox[1] * H + fs} fill={COLORS.TrustBoundary} fontSize={fs}>
                  {b.label || 'fronteira'}
                </text>
              </g>
            ) : null,
          )}

          {/* fluxos (setas): vermelho = cruza fronteira, cinza = não */}
          {edges.map((e, i) => {
            const s = byId.get(e.source)
            const t = byId.get(e.target)
            if (!s?.bbox || !t?.bbox) return null
            const [sx, sy] = center(s.bbox)
            const [tx, ty] = center(t.bbox)
            const col = e.crosses_boundary ? '#dc2626' : '#94a3b8'
            return (
              <line
                key={i}
                x1={sx * W}
                y1={sy * H}
                x2={tx * W}
                y2={ty * H}
                stroke={col}
                strokeWidth={e.crosses_boundary ? sw : sw * 0.7}
                markerEnd={`url(#arr-${e.crosses_boundary ? 0 : 1})`}
                opacity={0.85}
              />
            )
          })}

          {/* componentes (caixa por tipo + rótulo) */}
          {nodes.map((c) =>
            c.bbox ? (
              <g key={c.id}>
                <rect
                  x={c.bbox[0] * W}
                  y={c.bbox[1] * H}
                  width={c.bbox[2] * W}
                  height={c.bbox[3] * H}
                  fill="none"
                  stroke={COLORS[c.element_type] ?? COLORS.Process}
                  strokeWidth={sw}
                  rx={3}
                />
                <text
                  x={c.bbox[0] * W}
                  y={c.bbox[1] * H - sw}
                  fill={COLORS[c.element_type] ?? COLORS.Process}
                  fontSize={fs}
                  fontWeight={600}
                >
                  {c.canonical}
                </text>
              </g>
            ) : null,
          )}
        </svg>
      )}
    </div>
  )
}
