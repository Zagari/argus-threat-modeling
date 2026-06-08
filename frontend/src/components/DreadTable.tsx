import type { ThreatModel } from '../types'

const DIMS: [string, string][] = [
  ['damage', 'D'],
  ['reproducibility', 'R'],
  ['exploitability', 'E'],
  ['affected', 'A'],
  ['discoverability', 'Disc'],
]

const DIM_FULL: Record<string, string> = {
  damage: 'Damage — dano se explorada',
  reproducibility: 'Reproducibility — facilidade de repetir o ataque',
  exploitability: 'Exploitability — esforço/skill para explorar',
  affected: 'Affected — quantos usuários/quanto do sistema',
  discoverability: 'Discoverability — facilidade de descobrir a falha',
}

/** Tabela DREAD por ameaça (notas por dimensão + média + faixa), ordenada por risco. */
export default function DreadTable({ tm }: { tm: ThreatModel }) {
  const rows = tm.threats
    .filter((t) => t.dread_score != null)
    .slice()
    .sort((a, b) => (b.dread_score ?? 0) - (a.dread_score ?? 0))
  if (!rows.length) return null

  return (
    <div className="dread-table-wrap">
      <table className="threats dread-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Ameaça</th>
            <th>STRIDE</th>
            {DIMS.map(([k, l]) => (
              <th key={k} className="num" title={DIM_FULL[k]}>
                {l}
              </th>
            ))}
            <th className="num">Méd.</th>
            <th>Faixa</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}>
              <td>{t.id}</td>
              <td className="dread-title" title={t.title}>
                {t.title}
              </td>
              <td>{t.stride_category}</td>
              {DIMS.map(([k]) => (
                <td key={k} className="num">
                  {t.dread?.[k] ?? '—'}
                </td>
              ))}
              <td className="num">
                <strong>{t.dread_score}</strong>
              </td>
              <td>
                <span className={`dread-band b-${t.dread_band}`}>{t.dread_band}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
