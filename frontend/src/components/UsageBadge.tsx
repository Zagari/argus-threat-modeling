import type { Usage } from '../types'

function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

function fmtCost(u: Usage): string {
  if (u.mock) return 'mock'
  if (!u.cost_known || u.cost_usd <= 0) return 'custo n/d'
  return `~US$ ${u.cost_usd < 0.01 ? u.cost_usd.toFixed(4) : u.cost_usd.toFixed(2)}`
}

/** Selo de uso: tokens + custo estimado. Some quando não há chamadas reais. */
export default function UsageBadge({ u, label }: { u?: Usage | null; label?: string }) {
  if (!u || (u.calls === 0 && !u.mock)) return null
  return (
    <span className="usage" title={`${u.calls} chamada(s) · prompt ${u.prompt_tokens} · completion ${u.completion_tokens}`}>
      {label && <span className="usage-label">{label}</span>}
      <span className="usage-tok">{fmtTokens(u.total_tokens)} tok</span>
      <span className="usage-sep">·</span>
      <span className="usage-cost">{fmtCost(u)}</span>
    </span>
  )
}
