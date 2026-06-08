import { useRef, useState, type ReactNode } from 'react'
import { analyzeStream, downloadPdf } from '../api/client'
import DetectionOverlay from '../components/DetectionOverlay'
import DfdOverlay from '../components/DfdOverlay'
import StageCard, { type StageStatus } from '../components/StageCard'
import ThreatTable from '../components/ThreatTable'
import UsageBadge from '../components/UsageBadge'
import type { Capabilities, Component, Edge, StageEvent, ThreatModel, Usage } from '../types'

// ── Máquina de estados dos eventos SSE ───────────────────────────────────────
type SKey = 'e1' | 'ocr' | 'fusion' | 'crosscheck' | 'topology' | 'e3' | 'e4'

interface PipeState {
  name: string
  status: Record<SKey, StageStatus>
  current: SKey | null
  data: Partial<Record<SKey, StageEvent>>
  components: Component[]
  edges: Edge[]
  tm: ThreatModel | null
  errorMsg: string | null
}

function initState(): PipeState {
  return {
    name: '',
    status: { e1: 'idle', ocr: 'idle', fusion: 'idle', crosscheck: 'idle', topology: 'idle', e3: 'idle', e4: 'idle' },
    current: null,
    data: {},
    components: [],
    edges: [],
    tm: null,
    errorMsg: null,
  }
}

function reduce(prev: PipeState, stage: string, d: StageEvent): PipeState {
  const s: PipeState = { ...prev, status: { ...prev.status }, data: { ...prev.data } }
  const start = (k: SKey) => {
    s.status[k] = 'running'
    s.current = k
  }
  switch (stage) {
    case 'start':
      s.name = d.system_name ?? ''
      start('e1')
      break
    case 'e1':
      s.status.e1 = 'done'
      s.data.e1 = d
      if (d.components) s.components = d.components
      start('ocr')
      break
    case 'e2_ocr':
      s.status.ocr = d.ocr_used ? 'done' : 'skipped'
      s.data.ocr = d
      start('fusion')
      break
    case 'e2_fusion':
      s.status.fusion = d.fused ? 'done' : 'skipped'
      s.data.fusion = d
      if (d.components) s.components = d.components
      start('crosscheck')
      break
    case 'e2_crosscheck':
      s.status.crosscheck = d.crosscheck_used ? 'done' : 'skipped'
      s.data.crosscheck = d
      if (d.components) s.components = d.components
      start('topology')
      break
    case 'e2_topology':
      s.status.topology = 'done'
      s.data.topology = d
      if (d.components) s.components = d.components
      if (d.edges) s.edges = d.edges
      start('e3')
      break
    case 'e3_dfd':
      s.status.e3 = 'done'
      s.data.e3 = d
      if (d.components) s.components = d.components
      if (d.edges) s.edges = d.edges
      start('e4')
      break
    case 'e4_stride':
      s.status.e4 = 'done'
      s.data.e4 = d
      s.current = null
      break
    case 'done':
      if (d.threat_model) s.tm = d.threat_model
      s.current = null
      break
    case 'error':
      s.errorMsg = d.message ?? 'erro no pipeline'
      if (s.current) s.status[s.current] = 'error'
      s.current = null
      break
  }
  return s
}

function e2GroupStatus(st: PipeState): StageStatus {
  const subs: SKey[] = ['ocr', 'fusion', 'crosscheck', 'topology']
  if (subs.some((k) => st.status[k] === 'error')) return 'error'
  if (st.status.topology === 'done') return 'done'
  if (st.status.e1 === 'done') return 'running'
  return 'idle'
}

function e2Elapsed(st: PipeState): number | undefined {
  const subs: SKey[] = ['ocr', 'fusion', 'crosscheck', 'topology']
  const vals = subs.map((k) => st.data[k]?.elapsed_s).filter((v): v is number => v != null)
  return vals.length ? vals.reduce((a, b) => a + b, 0) : undefined
}

// ── Sub-card de uma etapa do E2 ──────────────────────────────────────────────
const SUB_ICON: Record<StageStatus, string> = { idle: '·', running: '⏳', done: '✓', error: '✗', skipped: '—' }

function SubStep({ status, title, children }: { status: StageStatus; title: string; children: ReactNode }) {
  return (
    <div className={`substep s-${status}`}>
      <div className="substep-head">
        <span className={`stage-status s-${status}`}>{SUB_ICON[status]}</span>
        <span>{title}</span>
      </div>
      <div className="substep-body muted">{children}</div>
    </div>
  )
}

export default function Argus({ caps }: { caps: Capabilities | null }) {
  const argusMl = caps?.argus_ml ?? false
  const rate = caps?.usd_brl_rate ?? 6
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [st, setSt] = useState<PipeState>(initState)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  function onPick(f: File | null) {
    setFile(f)
    setSt(initState())
    setError(null)
    setPreview(f ? URL.createObjectURL(f) : null)
  }

  async function run() {
    if (!file) return
    setError(null)
    setSt(initState())
    setRunning(true)
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      await analyzeStream(file, 'argus', (stage, data) => setSt((prev) => reduce(prev, stage, data)), ctrl.signal)
    } catch (e) {
      if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const started = running || st.status.e1 !== 'idle'
  const showDfd = st.status.e3 === 'done'
  const showDet = st.status.e1 === 'done' && !showDfd
  const sum: Record<string, unknown> = st.data.e3?.summary ?? {}
  const sv = (k: string): string => (sum[k] != null ? String(sum[k]) : '—')

  const ocrTexts = (st.data.ocr?.text_regions ?? []).map((r) => r.text).filter(Boolean)
  const labeled = (st.data.fusion?.components ?? []).filter((c) => c.label)

  return (
    <div className="full">
      <div className="card">
        <div className="system-head">
          <h2 style={{ margin: 0, fontSize: 18 }}>ARGUS</h2>
          <span className="badge cat">especialista · pipeline auditável</span>
        </div>
        <p className="muted" style={{ marginTop: 4 }}>
          Pipeline auditável: cada estágio expõe seu resultado parcial ao vivo (streaming).
        </p>

        {!argusMl && (
          <div className="banner-mock" style={{ marginTop: 8 }}>
            ⚠️ <strong>ARGUS indisponível neste ambiente (modo LITE).</strong> Requer o detector + deps de ML
            (<code>ARGUS_ML=true</code> e <code>ARGUS_DETECTOR_HF</code>). Veja o README → “Modos de implantação”. O
            Cíclope continua disponível na aba ao lado.
          </div>
        )}

        <label>Diagrama de arquitetura (imagem)</label>
        <input
          type="file"
          accept="image/*"
          disabled={!argusMl}
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        />
        <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
          <button className="primary" disabled={!argusMl || !file || running} onClick={run}>
            {running ? 'Executando pipeline…' : 'Analisar com ARGUS'}
          </button>
          {running && (
            <button className="ghost" onClick={() => abortRef.current?.abort()}>
              Cancelar
            </button>
          )}
        </div>
        {running && (
          <div className="muted" style={{ marginTop: 8 }}>
            Detecção + OCR + VLM (cross-check, topologia, STRIDE) — pode levar ~1–2&nbsp;min. Os cards abaixo se
            preenchem conforme cada estágio conclui.
          </div>
        )}
        {(error || st.errorMsg) && <div className="error">{error ?? st.errorMsg}</div>}
      </div>

      {preview && (
        <div className="card preview">
          <label>{showDfd ? 'DFD recuperado (E1–E3)' : showDet ? 'Detecções (E1)' : 'Diagrama enviado'}</label>
          {showDfd ? (
            <DfdOverlay src={preview} components={st.components} edges={st.edges} />
          ) : showDet ? (
            <DetectionOverlay src={preview} components={st.components} />
          ) : (
            <img src={preview} alt="diagrama" />
          )}
          {showDfd && (
            <p className="kv" style={{ marginTop: 8 }}>
              <span style={{ color: '#dc2626', fontWeight: 700 }}>—</span> fluxo que cruza fronteira ·{' '}
              <span style={{ color: '#a855f7', fontWeight: 700 }}>┄</span> fronteira de confiança
            </p>
          )}
        </div>
      )}

      {st.tm && (
        <div className="card summary-card">
          <span className="summary-title">Resumo da análise</span>
          <span className="summary-item">{st.tm.threats.length} ameaças</span>
          {st.tm.meta.groundedness != null && (
            <span className="summary-item">
              {Math.round(Number(st.tm.meta.groundedness) * 100)}% ancoradas
            </span>
          )}
          {st.tm.meta.latency_s != null && <span className="summary-item">{String(st.tm.meta.latency_s)}s</span>}
          <span style={{ marginLeft: 'auto' }}>
            <UsageBadge u={st.tm.meta.usage as Usage | undefined} label="custo total" rate={rate} />
          </span>
        </div>
      )}

      {started && (
        <>
          {/* ── E1 ── */}
          <StageCard
            title="E1 · Detecção (YOLO11)"
            status={st.status.e1}
            elapsed={st.data.e1?.elapsed_s}
            subtitle={st.status.e1 === 'done' ? `${st.data.e1?.components?.length ?? 0} componentes` : undefined}
          >
            {st.data.e1 ? (
              <>
                <p className="kv">
                  modelo: {String(st.data.e1.model?.weights ?? '—')} · imgsz: {String(st.data.e1.model?.imgsz ?? '—')}{' '}
                  · conf: {String(st.data.e1.model?.conf ?? '—')}
                </p>
                <table className="threats compact">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Classe canônica</th>
                      <th>Tipo DFD</th>
                      <th>Conf.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(st.data.e1.components ?? []).map((c) => (
                      <tr key={c.id}>
                        <td>{c.id}</td>
                        <td>{c.canonical}</td>
                        <td>{c.element_type}</td>
                        <td>{c.confidence != null ? `${Math.round(c.confidence * 100)}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <p className="muted">Detectando componentes…</p>
            )}
          </StageCard>

          {/* ── E2 (4 sub-etapas) ── */}
          <StageCard
            title="E2 · Leitura & Topologia"
            status={e2GroupStatus(st)}
            elapsed={e2Elapsed(st)}
            subtitle="OCR · fusão · cross-check · topologia"
          >
            <div className="substeps">
              <SubStep status={st.status.ocr} title="OCR">
                {st.status.ocr === 'skipped' ? (
                  'OCR indisponível neste ambiente.'
                ) : st.data.ocr ? (
                  <>
                    <div>{st.data.ocr.n_text ?? 0} regiões de texto lidas.</div>
                    {ocrTexts.length > 0 && (
                      <div className="taglist">
                        {ocrTexts.slice(0, 10).map((t, i) => (
                          <span key={i} className="tag">
                            {t}
                          </span>
                        ))}
                        {ocrTexts.length > 10 && <span className="tag more">+{ocrTexts.length - 10}</span>}
                      </div>
                    )}
                  </>
                ) : (
                  'aguardando…'
                )}
              </SubStep>

              <SubStep status={st.status.fusion} title="Fusão ícone↔rótulo">
                {st.status.fusion === 'skipped' ? (
                  'Sem textos para fundir.'
                ) : st.data.fusion ? (
                  <>
                    <div>{st.data.fusion.n_labeled ?? labeled.length} componentes rotulados.</div>
                    {labeled.length > 0 && (
                      <div className="taglist">
                        {labeled.slice(0, 8).map((c) => (
                          <span key={c.id} className="tag">
                            {c.canonical}: <strong>{c.label}</strong>
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  'aguardando…'
                )}
              </SubStep>

              <SubStep status={st.status.crosscheck} title="Cross-check (VLM)">
                {st.status.crosscheck === 'skipped' ? (
                  'Cross-check desligado (ARGUS_CROSSCHECK=0).'
                ) : st.data.crosscheck ? (
                  <>
                    <div>
                      {(st.data.crosscheck.added ?? 0) > 0 ? (
                        <span className="hl-add">+{st.data.crosscheck.added} propostos pelo VLM</span>
                      ) : (
                        'nenhum componente adicionado'
                      )}
                    </div>
                    <div>Corrige classes incertas e propõe componentes/fronteiras faltantes.</div>
                    <UsageBadge u={st.data.crosscheck.usage_delta} label="VLM" rate={rate} />
                  </>
                ) : (
                  'aguardando…'
                )}
              </SubStep>

              <SubStep status={st.status.topology} title="Topologia (VLM)">
                {st.data.topology ? (
                  <>
                    <div>{st.data.topology.n_edges ?? st.edges.length} fluxos extraídos.</div>
                    {st.edges.length > 0 && (
                      <div className="taglist">
                        {st.edges.slice(0, 8).map((e, i) => (
                          <span key={i} className="tag">
                            {e.source}→{e.target}
                          </span>
                        ))}
                        {st.edges.length > 8 && <span className="tag more">+{st.edges.length - 8}</span>}
                      </div>
                    )}
                    <UsageBadge u={st.data.topology.usage_delta} label="VLM" rate={rate} />
                  </>
                ) : (
                  'aguardando…'
                )}
              </SubStep>
            </div>
          </StageCard>

          {/* ── E3 ── */}
          <StageCard
            title="E3 · DFD (fronteiras de confiança)"
            status={st.status.e3}
            elapsed={st.data.e3?.elapsed_s}
            subtitle={st.status.e3 === 'done' ? `${sv('boundaries')} fronteiras · ${sv('crossing_flows')} cruzam` : undefined}
          >
            {st.data.e3 ? (
              <p className="kv">
                {st.components.length} componentes · {sv('boundaries')} fronteiras · {sv('crossing_flows')}/
                {st.edges.length} fluxos cruzam fronteira. A visualização do DFD está no diagrama acima.
              </p>
            ) : (
              <p className="muted">Montando o DFD…</p>
            )}
          </StageCard>

          {/* ── E4 ── */}
          <StageCard
            title="E4 · STRIDE-per-element"
            status={st.status.e4}
            elapsed={st.data.e4?.elapsed_s}
            subtitle={st.status.e4 === 'done' ? `${st.data.e4?.n_threats ?? 0} ameaças` : undefined}
          >
            {st.tm ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6, flexWrap: 'wrap' }}>
                  <span className="kv" style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span>
                      {st.tm.threats.length} ameaças · {String(st.tm.meta.model ?? '—')}
                      {st.tm.meta.latency_s != null ? ` · ${String(st.tm.meta.latency_s)}s total` : ''}
                    </span>
                    <UsageBadge u={st.data.e4?.usage_delta} label="STRIDE" rate={rate} />
                    <UsageBadge u={st.tm.meta.usage as Usage | undefined} label="total ARGUS" rate={rate} />
                  </span>
                  <button className="primary" onClick={() => downloadPdf(st.tm!).catch((e) => setError(String(e)))}>
                    Baixar PDF
                  </button>
                </div>
                <ThreatTable tm={st.tm} />
              </>
            ) : st.data.e4 ? (
              <p className="muted">{st.data.e4.n_threats ?? 0} ameaças geradas — montando o relatório…</p>
            ) : (
              <p className="muted">Gerando ameaças STRIDE-per-element…</p>
            )}
          </StageCard>
        </>
      )}

      {!started && argusMl && (
        <div className="card muted">
          Envie um diagrama e rode o <strong>ARGUS</strong> para acompanhar os estágios do pipeline ao vivo.
        </div>
      )}
    </div>
  )
}
