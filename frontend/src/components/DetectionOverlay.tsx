import type { Component, ElementType } from '../types'

// Cor por tipo DFD (mesma leitura visual do pipeline).
const COLORS: Record<ElementType, string> = {
  Process: '#3b82f6',
  DataStore: '#f59e0b',
  ExternalEntity: '#10b981',
  TrustBoundary: '#a855f7',
  DataFlow: '#64748b',
}

export default function DetectionOverlay({
  src,
  components,
  highlight,
}: {
  src: string
  components: Component[]
  highlight?: string | null
}) {
  return (
    <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', lineHeight: 0 }}>
      <img src={src} alt="diagrama" style={{ display: 'block', maxWidth: '100%' }} />
      {components.map((c) => {
        if (!c.bbox || c.bbox.length < 4) return null
        const [x, y, w, h] = c.bbox
        const color = COLORS[c.element_type] ?? COLORS.Process
        const on = highlight === c.id
        return (
          <div
            key={c.id}
            style={{
              position: 'absolute',
              left: `${x * 100}%`,
              top: `${y * 100}%`,
              width: `${w * 100}%`,
              height: `${h * 100}%`,
              border: `2px solid ${color}`,
              background: on ? `${color}22` : 'transparent',
              boxShadow: '0 0 0 1px rgba(0,0,0,.35)',
              borderRadius: 3,
              pointerEvents: 'none',
            }}
          >
            <span
              style={{
                position: 'absolute',
                top: -16,
                left: -1,
                background: color,
                color: '#fff',
                fontSize: 10,
                lineHeight: 1.4,
                padding: '0 4px',
                borderRadius: 3,
                whiteSpace: 'nowrap',
              }}
            >
              {c.canonical}
              {c.confidence != null ? ` ${Math.round(c.confidence * 100)}%` : ''}
            </span>
          </div>
        )
      })}
    </div>
  )
}
