import type { DetectStatus, DetectionResult, Settings, ThreatModel } from '../types'

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

export function updateSettings(
  body: Partial<{ provider: string; model: string; temperature: number; api_key: string; mock: boolean }>,
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
