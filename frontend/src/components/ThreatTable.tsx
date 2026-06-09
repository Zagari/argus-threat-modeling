import type { Threat, ThreatModel } from '../types'
import CitationLinks, { isControlId } from './CitationLinks'

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
            {groups[cat].map((t) => {
              const offensive = [...t.cwe_ids, ...t.capec_ids, ...t.attack_ids]
              const controls = Array.from(new Set(t.mitigations.flatMap((m) => m.refs).filter(isControlId)))
              return (
                <div className="threat" key={t.id}>
                  <strong>
                    {t.id} — {t.title}
                  </strong>{' '}
                  <span className={`badge ${sevClass(t.impact)}`}>{t.impact}</span>
                  <div className="meta">
                    Componente: {t.component_id} ({t.element_type}) · Prob.: {t.likelihood} · Risco: {t.risk_score}/25
                    {t.dread_score != null ? ` · DREAD ${t.dread_score} (${t.dread_band})` : ''}
                    {t.grounded ? ' · ancorada' : ''}
                  </div>
                  {offensive.length > 0 && (
                    <div className="meta">
                      <strong>Âncoras ofensivas:</strong> <CitationLinks ids={offensive} />
                    </div>
                  )}
                  {controls.length > 0 && (
                    <div className="meta">
                      <strong>Contramedidas:</strong> <CitationLinks ids={controls} />
                    </div>
                  )}
                  <div>{t.attack_scenario}</div>
                  {t.mitigations.length > 0 && (
                    <ul>
                      {t.mitigations.map((m, i) => {
                        const ctrls = m.refs.filter(isControlId)
                        return (
                          <li key={i}>
                            {m.description}
                            {ctrls.length ? (
                              <span className="refs">
                                {' ['}
                                <CitationLinks ids={ctrls} />
                                {']'}
                              </span>
                            ) : null}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>
                )
              })}
          </div>
        ) : null,
      )}
    </div>
  )
}
