import { useEffect, useState } from 'react'
import { getSettings, testSettings, updateSettings } from '../api/client'
import type { Settings } from '../types'

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null)
  const [provider, setProvider] = useState('gemini')
  const [model, setModel] = useState('')
  const [temperature, setTemperature] = useState(0.2)
  const [apiKey, setApiKey] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    const cur = await getSettings()
    setS(cur)
    setProvider(cur.provider)
    setModel(cur.model)
    setTemperature(cur.temperature)
  }

  useEffect(() => {
    load().catch((e) => setMsg({ ok: false, text: String(e) }))
  }, [])

  async function save() {
    setBusy(true)
    setMsg(null)
    try {
      const body: Record<string, unknown> = { provider, model, temperature }
      if (apiKey) body.api_key = apiKey
      const cur = await updateSettings(body)
      setS(cur)
      setApiKey('')
      setMsg({ ok: true, text: 'Configurações salvas.' })
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) })
    } finally {
      setBusy(false)
    }
  }

  async function test() {
    setBusy(true)
    setMsg(null)
    try {
      const r = await testSettings()
      setMsg({ ok: r.ok, text: r.message ?? (r.ok ? 'OK' : 'Falhou') })
    } catch (e) {
      setMsg({ ok: false, text: String(e) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <h2 style={{ marginTop: 0, fontSize: 16 }}>Configurações do LLM</h2>
      <p className="muted">A chave é mantida apenas no servidor (em memória) e nunca é exibida aqui.</p>

      <label>Provider</label>
      <select
        value={provider}
        onChange={(e) => {
          setProvider(e.target.value)
          setModel(s?.default_models[e.target.value] ?? '')
        }}
      >
        {(s?.available_providers ?? ['gemini', 'anthropic', 'openai']).map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      <label>Modelo (litellm id)</label>
      <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gemini/gemini-2.5-flash" />

      <label>Temperatura</label>
      <input
        type="number"
        step="0.1"
        min="0"
        max="1"
        value={temperature}
        onChange={(e) => setTemperature(Number(e.target.value))}
      />

      <label>Chave de API {s?.has_key ? '(já configurada — deixe em branco para manter)' : ''}</label>
      <input
        type="password"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder="cole a chave para definir/atualizar"
      />

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <button className="primary" disabled={busy} onClick={save}>
          Salvar
        </button>
        <button className="ghost" disabled={busy} onClick={test}>
          Testar conexão
        </button>
      </div>

      {msg && <div className={msg.ok ? 'ok' : 'error'}>{msg.text}</div>}
      {s && (
        <p className="kv" style={{ marginTop: 12 }}>
          Providers com chave: {s.providers_with_key.join(', ') || '—'} · mock: {String(s.mock)}
        </p>
      )}
    </div>
  )
}
