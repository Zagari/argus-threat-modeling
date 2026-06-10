import type {
  Capabilities,
  DetectStatus,
  DetectionResult,
  KnowledgeOptions,
  KnowledgeSearch,
  Settings,
  StageEvent,
  Subgraph,
  ThreatModel,
} from '../types'

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || r.statusText)
  }
  return (await r.json()) as T
}

export function getSettings(): Promise<Settings> {
  return fetch('/settings').then(j<Settings>)
}

export function getCapabilities(): Promise<Capabilities> {
  return fetch('/capabilities').then(j<Capabilities>)
}

export function updateSettings(
  body: Partial<{
    provider: string
    model: string
    temperature: number
    api_key: string
    mock: boolean
    usd_brl_rate: number
    cost_factor: number
  }>,
): Promise<Settings> {
  return fetch('/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(j<Settings>)
}

export function testSettings(): Promise<{ ok: boolean; message?: string; mock?: boolean }> {
  return fetch('/settings/test', { method: 'POST' }).then(j<{ ok: boolean; message?: string; mock?: boolean }>)
}

export async function analyze(file: File, system: string): Promise<ThreatModel> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`/analyze?system=${encodeURIComponent(system)}`, { method: 'POST', body: fd })
  return j<ThreatModel>(r)
}

/**
 * Roda a análise por streaming (SSE) e chama `onEvent(stage, data)` a cada estágio.
 * Usa POST + ReadableStream (o EventSource nativo não envia upload). Lança em erro de
 * transporte; o evento `error` (pipeline) também é entregue via `onEvent` para a UI tratar.
 */
export async function analyzeStream(
  file: File,
  system: string,
  onEvent: (stage: string, data: StageEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`/analyze/stream?system=${encodeURIComponent(system)}`, {
    method: 'POST',
    body: fd,
    signal,
  })
  if (!r.ok || !r.body) throw new Error((await r.text()) || r.statusText)

  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, i)
      buf = buf.slice(i + 2)
      let stage = 'message'
      const dataLines: string[] = []
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) stage = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
      }
      if (dataLines.length) onEvent(stage, JSON.parse(dataLines.join('\n')) as StageEvent)
    }
  }
}

export function getKnowledgeOptions(): Promise<KnowledgeOptions> {
  return fetch('/knowledge/options').then(j<KnowledgeOptions>)
}

export function getSubgraph(canonical: string, stride: string): Promise<Subgraph> {
  return fetch(`/knowledge/subgraph?canonical=${encodeURIComponent(canonical)}&stride=${encodeURIComponent(stride)}`).then(
    j<Subgraph>,
  )
}

export function getPanorama(canonical: string): Promise<Subgraph> {
  return fetch(`/knowledge/panorama?canonical=${encodeURIComponent(canonical)}`).then(j<Subgraph>)
}

export function searchKnowledge(q: string): Promise<KnowledgeSearch> {
  return fetch(`/knowledge/search?q=${encodeURIComponent(q)}`).then(j<KnowledgeSearch>)
}

export function detectStatus(): Promise<DetectStatus> {
  return fetch('/stage/detect/status').then(j<DetectStatus>)
}

export async function detectStage(file: File, conf?: number): Promise<DetectionResult> {
  const fd = new FormData()
  fd.append('file', file)
  const q = conf != null ? `?conf=${conf}` : ''
  const r = await fetch(`/stage/detect${q}`, { method: 'POST', body: fd })
  return j<DetectionResult>(r)
}

export async function downloadPdf(tm: ThreatModel): Promise<void> {
  const r = await fetch('/report/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tm),
  })
  if (!r.ok) throw new Error(await r.text())
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'relatorio-stride.pdf'
  a.click()
  URL.revokeObjectURL(url)
}
