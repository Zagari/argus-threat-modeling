import { useState } from 'react'
import { analyze, downloadPdf } from '../api/client'
import ThreatTable from '../components/ThreatTable'
import type { ThreatModel } from '../types'

export default function Analyze() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [system, setSystem] = useState('ciclope')
  const [tm, setTm] = useState<ThreatModel | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function onPick(f: File | null) {
    setFile(f)
    setTm(null)
    setError(null)
    setPreview(f ? URL.createObjectURL(f) : null)
  }

  async function run() {
    if (!file) return
    setLoading(true)
    setError(null)
    setTm(null)
    try {
      setTm(await analyze(file, system))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="row">
      <div className="col">
        <div className="card">
          <label>Diagrama de arquitetura (imagem)</label>
          <input type="file" accept="image/*" onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
          <label>Sistema</label>
          <select value={system} onChange={(e) => setSystem(e.target.value)}>
            <option value="ciclope">Cíclope (baseline LLM-only)</option>
            <option value="argus">ARGUS (especialista) — a partir da Fase 2</option>
          </select>
          <div style={{ marginTop: 14 }}>
            <button className="primary" disabled={!file || loading} onClick={run}>
              {loading ? 'Analisando…' : 'Analisar'}
            </button>
          </div>
          {error && <div className="error">{error}</div>}
        </div>
        {preview && (
          <div className="card preview">
            <label>Pré-visualização</label>
            <img src={preview} alt="diagrama" />
          </div>
        )}
      </div>

      <div className="col">
        {tm ? (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <h2 style={{ margin: 0, fontSize: 16, flex: 1 }}>{tm.system_name}</h2>
              <button className="ghost" onClick={() => downloadPdf(tm).catch((e) => setError(String(e)))}>
                Baixar PDF
              </button>
            </div>
            <p className="kv">
              origem: {String(tm.meta.system ?? '—')} · modelo: {String(tm.meta.provider ?? '—')}/
              {String(tm.meta.model ?? '—')}
              {tm.meta.latency_s != null ? ` · ${String(tm.meta.latency_s)}s` : ''}
            </p>
            <ThreatTable tm={tm} />
          </div>
        ) : (
          <div className="card muted">
            Envie um diagrama e clique em <strong>Analisar</strong> para ver o relatório STRIDE.
          </div>
        )}
      </div>
    </div>
  )
}
