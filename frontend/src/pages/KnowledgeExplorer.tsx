import { useEffect, useState } from 'react'
import { getKnowledgeOptions, getSubgraph, searchKnowledge } from '../api/client'
import { urlForId } from '../components/CitationLinks'
import KnowledgeSubgraph from '../components/KnowledgeSubgraph'
import type { KnowledgeOptions, KnowledgeSearch, Subgraph } from '../types'

export default function KnowledgeExplorer() {
  const [opts, setOpts] = useState<KnowledgeOptions | null>(null)
  const [canonical, setCanonical] = useState('api_gateway')
  const [stride, setStride] = useState('Spoofing')
  const [sg, setSg] = useState<Subgraph | null>(null)
  const [q, setQ] = useState('')
  const [search, setSearch] = useState<KnowledgeSearch | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getKnowledgeOptions()
      .then(setOpts)
      .catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    getSubgraph(canonical, stride)
      .then(setSg)
      .catch((e) => setError(String(e)))
  }, [canonical, stride])

  async function runSearch(e: React.FormEvent) {
    e.preventDefault()
    if (q.trim().length < 2) return
    try {
      setSearch(await searchKnowledge(q.trim()))
    } catch (err) {
      setError(String(err))
    }
  }

  return (
    <div className="full">
      <div className="card">
        <h2 style={{ margin: 0, fontSize: 18 }}>Base de conhecimento</h2>
        <p className="muted" style={{ marginTop: 4 }}>
          O grafo que ancora as ameaças do ARGUS: CWE (fraquezas) → CAPEC (padrões de ataque) e os controles ASVS, por
          (classe de componente × categoria STRIDE). Os mesmos catálogos usados na validação (groundedness).
        </p>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ minWidth: 220 }}>
            <label>Classe de componente</label>
            <select value={canonical} onChange={(e) => setCanonical(e.target.value)}>
              {(opts?.classes ?? [canonical]).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div style={{ minWidth: 220 }}>
            <label>Categoria STRIDE</label>
            <select value={stride} onChange={(e) => setStride(e.target.value)}>
              {(opts?.stride ?? [stride]).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      <div className="card">
        <label>
          Subgrafo de <strong>({canonical}, {stride})</strong> — clique num nó para abrir a fonte oficial
        </label>
        {sg ? <KnowledgeSubgraph sg={sg} /> : <p className="muted">Carregando subgrafo…</p>}
      </div>

      <div className="card">
        <form onSubmit={runSearch} style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label>Buscar no catálogo (por id ou nome)</label>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="ex.: authentication, injection, CWE-89"
            />
          </div>
          <button className="primary" type="submit">
            Buscar
          </button>
        </form>
        {search && search.hits.length > 0 && (
          <>
            <div className="kv" style={{ marginTop: 10 }}>
              Modo: <span className={`chip ${search.mode === 'semântica' ? 'ok' : ''}`}>{search.mode}</span>
              {search.mode === 'semântica' ? ' (por significado)' : ' (texto literal — índice semântico indisponível)'}
            </div>
            <table className="threats" style={{ marginTop: 8, fontSize: 13 }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Tipo</th>
                  <th>Nome</th>
                  {search.mode === 'semântica' && <th className="num">Relevância</th>}
                </tr>
              </thead>
              <tbody>
                {search.hits.map((h) => {
                  const url = h.url ?? urlForId(h.id)
                  return (
                    <tr key={`${h.kind}-${h.id}`}>
                      <td>{url ? <a className="cite" href={url} target="_blank" rel="noreferrer">{h.id}</a> : h.id}</td>
                      <td>{h.kind}</td>
                      <td>{h.name}</td>
                      {search.mode === 'semântica' && <td className="num">{h.score != null ? h.score.toFixed(2) : '—'}</td>}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}
