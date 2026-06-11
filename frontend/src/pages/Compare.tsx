import { useState } from 'react'
import { analyzeStream, compareDiff } from '../api/client'
import ThreatTable from '../components/ThreatTable'
import type { Capabilities, CompareResult, CompareSummary, StageEvent, ThreatModel } from '../types'

type SysState = { status: 'idle' | 'running' | 'done' | 'error'; stage: string; error: string | null }
const IDLE: SysState = { status: 'idle', stage: '', error: null }

/** Roda uma análise por streaming e resolve com o ThreatModel final (rejeita em erro do pipeline). */
function streamTm(file: File, system: string, onStage: (stage: string) => void): Promise<ThreatModel> {
  return new Promise((resolve, reject) => {
    let tm: ThreatModel | null = null
    analyzeStream(file, system, (stage: string, data: StageEvent) => {
      if (stage === 'error') {
        reject(new Error(data.message ?? 'erro no pipeline'))
        return
      }
      if (stage === 'done' && data.threat_model) tm = data.threat_model
      onStage(stage)
    })
      .then(() => (tm ? resolve(tm) : reject(new Error('sem resultado'))))
      .catch(reject)
  })
}

const pct = (x?: number | null) => (x == null ? '—' : `${Math.round(x * 100)}%`)
const dread = (d?: Record<string, number> | null) =>
  d ? `${d['Crítico'] ?? 0} / ${d['Alto'] ?? 0} / ${d['Médio'] ?? 0} / ${d['Baixo'] ?? 0}` : '—'

export default function Compare({ caps }: { caps: Capabilities | null }) {
  const argusMl = caps?.argus_ml ?? false
  const rate = caps?.usd_brl_rate ?? 6
  const factor = caps?.cost_factor ?? 1
  const brl = (usd?: number | null) => (usd == null ? '—' : `R$ ${(usd * rate * factor).toFixed(2)}`)

  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [c, setC] = useState<SysState>(IDLE)
  const [a, setA] = useState<SysState>(IDLE)
  const [cTm, setCTm] = useState<ThreatModel | null>(null)
  const [aTm, setATm] = useState<ThreatModel | null>(null)
  const [result, setResult] = useState<CompareResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function onPick(f: File | null) {
    setFile(f)
    setPreview(f ? URL.createObjectURL(f) : null)
    setResult(null)
    setC(IDLE)
    setA(IDLE)
    setCTm(null)
    setATm(null)
    setError(null)
  }

  async function run() {
    if (!file) return
    setError(null)
    setResult(null)
    setCTm(null)
    setATm(null)
    setC({ status: 'running', stage: 'start', error: null })
    setA({ status: 'running', stage: 'start', error: null })
    setRunning(true)
    const pc = streamTm(file, 'ciclope', (stage) => setC((s) => ({ ...s, stage })))
      .then((tm) => (setCTm(tm), setC((s) => ({ ...s, status: 'done' })), tm))
      .catch((e: Error) => {
        setC((s) => ({ ...s, status: 'error', error: e.message }))
        throw e
      })
    const pa = streamTm(file, 'argus', (stage) => setA((s) => ({ ...s, stage })))
      .then((tm) => (setATm(tm), setA((s) => ({ ...s, status: 'done' })), tm))
      .catch((e: Error) => {
        setA((s) => ({ ...s, status: 'error', error: e.message }))
        throw e
      })
    try {
      const [cm, am] = await Promise.all([pc, pa])
      setResult(await compareDiff(cm, am))
    } catch {
      setError('Uma das análises falhou — veja o status de cada sistema abaixo.')
    } finally {
      setRunning(false)
    }
  }

  const col = (label: string, sys: SysState) => (
    <div className="card system-card">
      <div className="system-head">
        <h3 style={{ margin: 0 }}>{label}</h3>
        <span className={`chip ${sys.status === 'done' ? 'ok' : sys.status === 'error' ? 'off' : 'warn'}`}>
          {sys.status === 'idle' ? '—' : sys.status === 'running' ? `rodando… (${sys.stage})` : sys.status}
        </span>
      </div>
      {sys.error && <div className="error">{sys.error}</div>}
    </div>
  )

  const metric = (label: string, cv: string | number, av: string | number, hl = false) => (
    <tr>
      <td>{label}</td>
      <td className="num">{cv}</td>
      <td className="num" style={hl ? { fontWeight: 700 } : undefined}>{av}</td>
    </tr>
  )

  const R = result
  const cs: CompareSummary | undefined = R?.ciclope
  const as: CompareSummary | undefined = R?.argus

  return (
    <div className="full">
      <div className="card">
        <div className="system-head">
          <h2 style={{ margin: 0, fontSize: 18 }}>Comparar — Cíclope × ARGUS</h2>
          <span className="badge cat">estudo lado a lado</span>
        </div>
        <p className="muted" style={{ marginTop: 4 }}>
          Roda os <strong>dois sistemas no mesmo diagrama</strong> (em paralelo) e mede ambos com a{' '}
          <strong>mesma régua</strong>. A métrica-chave é a <strong>groundedness</strong>: o ARGUS recupera e
          valida as âncoras; o Cíclope cita da memória do modelo (e pode alucinar IDs).
        </p>

        {!argusMl && (
          <div className="banner-mock" style={{ marginTop: 8 }}>
            ⚠️ <strong>Comparação indisponível neste ambiente (modo LITE)</strong> — o ARGUS requer o detector + deps de ML.
          </div>
        )}

        <label>Diagrama de arquitetura (imagem)</label>
        <input type="file" accept="image/*" disabled={!argusMl} onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
        <div style={{ marginTop: 14 }}>
          <button className="primary" disabled={!argusMl || !file || running} onClick={run}>
            {running ? 'Comparando (Cíclope + ARGUS)…' : 'Comparar os dois sistemas'}
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

      {(c.status !== 'idle' || a.status !== 'idle') && (
        <div className="systems">
          {col('Cíclope', c)}
          {col('ARGUS', a)}
        </div>
      )}

      {R && cs && as && (
        <>
          <div className="card summary-card" style={{ alignItems: 'stretch' }}>
            <div style={{ flex: 1 }}>
              <div className="summary-title">Cíclope — groundedness</div>
              <div style={{ fontSize: 30, fontWeight: 800, color: (cs.groundedness ?? 0) >= 0.8 ? '#1c7a3a' : '#d9534f' }}>
                {pct(cs.groundedness)}
              </div>
              <div className="muted">{cs.ids_invalid ?? 0} ID(s) alucinado(s)</div>
            </div>
            <div style={{ flex: 1 }}>
              <div className="summary-title">ARGUS — groundedness</div>
              <div style={{ fontSize: 30, fontWeight: 800, color: (as.groundedness ?? 0) >= 0.8 ? '#1c7a3a' : '#d9534f' }}>
                {pct(as.groundedness)}
              </div>
              <div className="muted">{as.ids_invalid ?? 0} ID(s) alucinado(s) · {as.n_cves} CVEs reais</div>
            </div>
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Métricas</h3>
            <table className="threats compact">
              <thead>
                <tr><th>Métrica</th><th className="num">Cíclope</th><th className="num">ARGUS</th></tr>
              </thead>
              <tbody>
                {metric('Ameaças', cs.n_threats, as.n_threats)}
                {metric('Groundedness', pct(cs.groundedness), pct(as.groundedness), true)}
                {metric('Validade de IDs', pct(cs.id_validity), pct(as.id_validity))}
                {metric('IDs alucinados', cs.ids_invalid ?? '—', as.ids_invalid ?? '—')}
                {metric('CVEs reais (NVD)', cs.n_cves, as.n_cves)}
                {metric('DREAD (Crít/Alto/Méd/Baixo)', dread(cs.dread_dist), dread(as.dread_dist))}
                {metric('Latência', cs.latency_s != null ? `${cs.latency_s}s` : '—', as.latency_s != null ? `${as.latency_s}s` : '—')}
                {metric('Custo', brl(cs.cost_usd), brl(as.cost_usd))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Diferenças por (classe × STRIDE)</h3>
            <p className="muted">
              <span className="badge low">comuns {R.diff.n_common}</span>{' '}
              <span className="badge high">só-ARGUS {R.diff.n_only_argus}</span>{' '}
              <span className="badge med">só-Cíclope {R.diff.n_only_ciclope}</span>
            </p>
            {R.diff.only_argus.length > 0 && (
              <p className="muted" style={{ fontSize: 12 }}>
                <strong>Só o ARGUS apontou:</strong>{' '}
                {R.diff.only_argus.map((s) => `${s.canonical}/${s.stride}`).join(' · ')}
              </p>
            )}
            {R.diff.only_ciclope.length > 0 && (
              <p className="muted" style={{ fontSize: 12 }}>
                <strong>Só o Cíclope apontou:</strong>{' '}
                {R.diff.only_ciclope.map((s) => `${s.canonical}/${s.stride}`).join(' · ')}
              </p>
            )}
          </div>

          {cTm && aTm && (
            <div className="systems">
              <div className="card system-card">
                <h3 style={{ marginTop: 0 }}>Ameaças — Cíclope ({cTm.threats.length})</h3>
                <ThreatTable tm={cTm} />
              </div>
              <div className="card system-card">
                <h3 style={{ marginTop: 0 }}>Ameaças — ARGUS ({aTm.threats.length})</h3>
                <ThreatTable tm={aTm} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
