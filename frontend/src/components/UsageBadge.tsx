import type { Usage } from '../types'

function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

function fmtBRL(value: number): string {
  const digits = value < 0.1 ? 4 : 2
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: digits,
  })
}

function fmtCost(u: Usage, rate: number, factor: number): string {
  if (u.mock) return 'mock'
  if (!u.cost_known || u.cost_usd <= 0) return 'custo n/d'
  // R$ = custo estimado (US$) × cotação × fator de calibração (câmbio/IOF/tabela do litellm)
  return `~${fmtBRL(u.cost_usd * rate * factor)}`
}

/** Selo de uso: tokens + custo estimado em R$ (cost_usd × cotação × fator). Some sem chamadas reais. */
export default function UsageBadge({
  u,
  label,
  rate = 6,
  factor = 1,
}: {
  u?: Usage | null
  label?: string
  rate?: number
  factor?: number
}) {
  if (!u || (u.calls === 0 && !u.mock)) return null
  const tip =
    `${u.calls} chamada(s) · prompt ${u.prompt_tokens} · completion ${u.completion_tokens} · ` +
    `~US$ ${u.cost_usd.toFixed(4)} × R$ ${rate.toFixed(2)}/US$${factor !== 1 ? ` × ${factor.toFixed(2)} (ajuste)` : ''}`
  return (
    <span className="usage" title={tip}>
      {label && <span className="usage-label">{label}</span>}
      <span className="usage-tok">{fmtTokens(u.total_tokens)} tok</span>
      <span className="usage-sep">·</span>
      <span className="usage-cost">{fmtCost(u, rate, factor)}</span>
    </span>
  )
}
