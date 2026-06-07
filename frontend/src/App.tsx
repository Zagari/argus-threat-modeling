import { useEffect, useState } from 'react'
import { getCapabilities } from './api/client'
import Argus from './pages/Argus'
import Ciclope from './pages/Ciclope'
import Home from './pages/Home'
import SettingsPage from './pages/Settings'
import type { Capabilities } from './types'

type Tab = 'home' | 'ciclope' | 'argus' | 'settings'

export default function App() {
  const [tab, setTab] = useState<Tab>('home')
  const [caps, setCaps] = useState<Capabilities | null>(null)

  function refreshCaps() {
    getCapabilities()
      .then(setCaps)
      .catch(() => setCaps(null))
  }

  // Recarrega capacidades ao voltar para Início/Configurações (o mock pode ter mudado).
  useEffect(refreshCaps, [tab === 'home' || tab === 'settings'])

  const mock = caps?.llm.mock ?? false

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>ARGUS &amp; Cíclope</h1>
          <div className="sub">Modelagem de ameaças STRIDE a partir de diagramas de arquitetura</div>
        </div>
        <nav className="tabs">
          <button className={tab === 'home' ? 'active' : ''} onClick={() => setTab('home')}>
            Início
          </button>
          <button className={tab === 'ciclope' ? 'active' : ''} onClick={() => setTab('ciclope')}>
            Cíclope
          </button>
          <button className={tab === 'argus' ? 'active' : ''} onClick={() => setTab('argus')}>
            ARGUS
          </button>
          <button className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>
            Configurações
          </button>
        </nav>
      </header>
      {mock && (
        <div className="banner-mock">
          ⚠️ <strong>Modo de exemplo (mock)</strong> — o resultado é ilustrativo e fixo; <em>não</em> é uma
          análise real do diagrama. Configure uma chave de LLM e desligue o mock para análise real.
        </div>
      )}
      {tab === 'home' && <Home caps={caps} onNavigate={setTab} />}
      {tab === 'ciclope' && <Ciclope />}
      {tab === 'argus' && <Argus caps={caps} />}
      {tab === 'settings' && <SettingsPage />}
    </div>
  )
}
