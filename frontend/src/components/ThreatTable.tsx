import type { Threat, ThreatModel } from '../types'

const ORDER: string[] = [
  'Spoofing',
  'Tampering',
  'Repudiation',
  'Information Disclosure',
  'Denial of Service',
  'Elevation of Privilege',
]

function sevClass(impact: string): string {
  const map: Record<string, string> = { Critical: 'crit', High: 'high', Medium: 'med', Low: 'low' }
  return map[impact] ?? 'low'
}

export default function ThreatTable({ tm }: { tm: ThreatModel }) {
  const groups: Record<string, Threat[]> = {}
  for (const cat of ORDER) groups[cat] = []
  for (const t of tm.threats) (groups[t.stride_category] ??= []).push(t)

  return (
    <div>
      <p className="muted">
        {tm.components.length} componentes · {tm.edges.length} fluxos · {tm.threats.length} ameaças
      </p>
      {ORDER.map((cat) =>
        groups[cat] && groups[cat].length > 0 ? (
          <div key={cat}>
            <h3 style={{ fontSize: 14, margin: '14px 0 6px' }}>
              <span className="badge cat">{cat}</span> <span className="muted">({groups[cat].length})</span>
            </h3>
            {groups[cat].map((t) => (
              <div className="threat" key={t.id}>
                <strong>
                  {t.id} — {t.title}
                </strong>{' '}
                <span className={`badge ${sevClass(t.impact)}`}>{t.impact}</span>
                <div className="meta">
                  Componente: {t.component_id} ({t.element_type}) · Prob.: {t.likelihood} · Risco: {t.risk_score}/25
                  {t.cwe_ids.length ? ` · ${t.cwe_ids.join(', ')}` : ''}
                  {t.grounded ? ' · ancorada' : ''}
                </div>
                <div>{t.attack_scenario}</div>
                {t.mitigations.length > 0 && (
                  <ul>
                    {t.mitigations.map((m, i) => (
                      <li key={i}>
                        {m.description}
                        {m.refs.length ? <span className="refs"> [{m.refs.join(', ')}]</span> : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        ) : null,
      )}
    </div>
  )
}
