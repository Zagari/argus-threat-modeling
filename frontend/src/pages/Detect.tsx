import { useEffect, useState } from 'react'
import { detectStage, detectStatus } from '../api/client'
import DetectionOverlay from '../components/DetectionOverlay'
import type { DetectStatus, DetectionResult } from '../types'

export default function Detect() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [res, setRes] = useState<DetectionResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<DetectStatus | null>(null)
  const [hover, setHover] = useState<string | null>(null)

  useEffect(() => {
    detectStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [])

  function onPick(f: File | null) {
    setFile(f)
    setRes(null)
    setError(null)
    setPreview(f ? URL.createObjectURL(f) : null)
  }

  async function run() {
    if (!file) return
    setLoading(true)
    setError(null)
    setRes(null)
    try {
      setRes(await detectStage(file))
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
          <div style={{ marginTop: 14 }}>
            <button className="primary" disabled={!file || loading} onClick={run}>
              {loading ? 'Detectando…' : 'Detectar componentes (E1)'}
            </button>
          </div>
          {status && !status.available && (
            <div className="banner-mock" style={{ marginTop: 12 }}>
              ⚠️ Detector E1 indisponível neste ambiente. {status.reason}
            </div>
          )}
          {error && <div className="error">{error}</div>}
        </div>

        {preview && (
          <div className="card preview">
            <label>{res ? 'Detecções (E1)' : 'Pré-visualização'}</label>
            {res ? (
              <DetectionOverlay src={preview} components={res.components} highlight={hover} />
            ) : (
              <img src={preview} alt="diagrama" />
            )}
          </div>
        )}
      </div>

      <div className="col">
        {res ? (
          <div className="card">
            <h2 style={{ margin: '0 0 8px', fontSize: 16 }}>
              {res.components.length} componente(s) detectado(s)
            </h2>
            <p className="kv">
              modelo: {String(res.model.weights ?? '—')} · imgsz: {String(res.model.imgsz ?? '—')} · conf:{' '}
              {String(res.model.conf ?? '—')}
            </p>
            <table className="threats">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Classe canônica</th>
                  <th>Tipo DFD</th>
                  <th>Confiança</th>
                </tr>
              </thead>
              <tbody>
                {res.components.map((c) => (
                  <tr key={c.id} onMouseEnter={() => setHover(c.id)} onMouseLeave={() => setHover(null)}>
                    <td>{c.id}</td>
                    <td>{c.canonical}</td>
                    <td>{c.element_type}</td>
                    <td>{c.confidence != null ? `${Math.round(c.confidence * 100)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card muted">
            Envie um diagrama e clique em <strong>Detectar</strong> para ver os componentes (estágio E1 do ARGUS).
          </div>
        )}
      </div>
    </div>
  )
}
