import { useState } from 'react'
import { analyze } from '../api/client'
import DfdOverlay from '../components/DfdOverlay'
import ThreatTable from '../components/ThreatTable'
import type { ThreatModel } from '../types'

export default function Pipeline() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
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
      setTm(await analyze(file, 'argus'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const m: Record<string, unknown> = tm?.meta ?? {}
  const s = (k: string): string => (m[k] != null ? String(m[k]) : '—')

  return (
    <div className="row">
      <div className="col">
        <div className="card">
          <label>Diagrama de arquitetura (imagem)</label>
          <input type="file" accept="image/*" onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
          <div style={{ marginTop: 14 }}>
            <button className="primary" disabled={!file || loading} onClick={run}>
              {loading ? 'Executando pipeline…' : 'Analisar com ARGUS (E1→E4)'}
            </button>
          </div>
          {loading && (
            <div className="muted" style={{ marginTop: 8 }}>
              O pipeline especialista roda detecção + OCR + VLM (cross-check, topologia, STRIDE) — pode levar
              ~1–2&nbsp;min.
            </div>
          )}
          {error && <div className="error">{error}</div>}
        </div>

        {preview && (
          <div className="card preview">
            <label>{tm ? 'DFD recuperado (E1–E3)' : 'Pré-visualização'}</label>
            {tm ? (
              <DfdOverlay src={preview} components={tm.components} edges={tm.edges} />
            ) : (
              <img src={preview} alt="diagrama" />
            )}
            {tm && (
              <p className="kv" style={{ marginTop: 8 }}>
                <span style={{ color: '#dc2626', fontWeight: 700 }}>—</span> fluxo que cruza fronteira de confiança ·{' '}
                <span style={{ color: '#a855f7', fontWeight: 700 }}>┄</span> fronteira de confiança
              </p>
            )}
          </div>
        )}
      </div>

      <div className="col">
        {tm ? (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <h2 style={{ margin: 0, fontSize: 16, flex: 1 }}>{tm.system_name}</h2>
              <span className="badge cat">ARGUS</span>
            </div>
            <p className="kv">
              {tm.components.length} componentes · {s('boundaries')} fronteiras · {s('crossing_flows')}/{tm.edges.length}{' '}
              fluxos cruzam · {tm.threats.length} ameaças
              {m.latency_s != null ? ` · ${s('latency_s')}s` : ''} · {s('model')}
            </p>
            <ThreatTable tm={tm} />
          </div>
        ) : (
          <div className="card muted">
            Envie um diagrama e rode o <strong>ARGUS</strong> para ver o DFD extraído (componentes, fronteiras e
            fluxos) e as ameaças STRIDE-per-element.
          </div>
        )}
      </div>
    </div>
  )
}
