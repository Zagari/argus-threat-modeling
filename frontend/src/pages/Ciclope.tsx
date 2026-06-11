import { useState } from 'react'
import { analyze, downloadPdf, imageKey } from '../api/client'
import ThreatTable from '../components/ThreatTable'
import UsageBadge from '../components/UsageBadge'
import type { ThreatModel, Usage } from '../types'

export default function Ciclope({
  rate = 6,
  factor = 1,
  onResult,
}: {
  rate?: number
  factor?: number
  onResult?: (tm: ThreatModel, key: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [systemName, setSystemName] = useState('')
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
      const result = await analyze(file, 'ciclope', systemName)
      setTm(result)
      onResult?.(result, imageKey(file)) // Lote 2: disponibiliza p/ a aba Comparar reaproveitar
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="full">
      <div className="card">
        <div className="system-head">
          <h2 style={{ margin: 0, fontSize: 18 }}>Cíclope</h2>
          <span className="badge cat">baseline · LLM-only</span>
        </div>
        <p className="muted" style={{ marginTop: 4 }}>
          A imagem vai direto a um VLM, que extrai componentes, conexões e ameaças STRIDE numa única passagem.
        </p>
        <label>Diagrama de arquitetura (imagem)</label>
        <input type="file" accept="image/*" onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
        <label>Nome do sistema (opcional)</label>
        <input
          type="text"
          value={systemName}
          onChange={(e) => setSystemName(e.target.value)}
          placeholder="se vazio, o modelo nomeia a partir do diagrama"
        />
        <div style={{ marginTop: 14 }}>
          <button className="primary" disabled={!file || loading} onClick={run}>
            {loading ? 'Analisando…' : 'Analisar'}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      {preview && (
        <div className="card preview">
          <label>Diagrama enviado</label>
          <img src={preview} alt="diagrama" />
        </div>
      )}

      {tm && (
        <div className="card summary-card">
          <span className="summary-title">Resumo da análise</span>
          <span className="summary-item">{tm.threats.length} ameaças</span>
          {tm.meta.latency_s != null && <span className="summary-item">{String(tm.meta.latency_s)}s</span>}
          <span style={{ marginLeft: 'auto' }}>
            <UsageBadge u={tm.meta.usage as Usage | undefined} label="custo total" rate={rate} factor={factor} />
          </span>
        </div>
      )}

      {tm && (
        <div className="card">
          {(tm.meta.mock === true || tm.meta.provider === 'mock') && (
            <div className="banner-mock" style={{ marginBottom: 10 }}>
              Resultado de exemplo (mock) — não reflete o diagrama enviado.
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h2 style={{ margin: 0, fontSize: 16, flex: 1 }}>{tm.system_name}</h2>
            <button className="primary" onClick={() => downloadPdf(tm).catch((e) => setError(String(e)))}>
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
      )}

      {!preview && !tm && (
        <div className="card muted">
          Envie um diagrama e clique em <strong>Analisar</strong> para ver o relatório STRIDE do Cíclope.
        </div>
      )}
    </div>
  )
}
