import { useState, type ReactNode } from 'react'

export type StageStatus = 'idle' | 'running' | 'done' | 'error' | 'skipped'

const ICON: Record<StageStatus, string> = {
  idle: '·',
  running: '⏳',
  done: '✓',
  error: '✗',
  skipped: '—',
}

/** Card dobrável de um estágio do pipeline. Aberto por padrão; mostra status e tempo. */
export default function StageCard({
  title,
  subtitle,
  status,
  elapsed,
  defaultOpen = true,
  children,
}: {
  title: string
  subtitle?: ReactNode
  status: StageStatus
  elapsed?: number
  defaultOpen?: boolean
  children?: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={`stage-card stage-${status}`}>
      <button className="stage-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="stage-caret">{open ? '▼' : '►'}</span>
        <span className={`stage-status s-${status}`}>
          {status === 'running' ? <span className="spinner">⏳</span> : ICON[status]}
        </span>
        <span className="stage-title">{title}</span>
        {subtitle != null && <span className="stage-sub">{subtitle}</span>}
        {elapsed != null && <span className="stage-time">{elapsed.toFixed(1)}s</span>}
      </button>
      {open && children != null && <div className="stage-body">{children}</div>}
    </div>
  )
}
