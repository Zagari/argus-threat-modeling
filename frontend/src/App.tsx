import { useEffect, useState } from 'react'
import { getCapabilities } from './api/client'
import Argus from './pages/Argus'
import Ciclope from './pages/Ciclope'
import Compare from './pages/Compare'
import Home from './pages/Home'
import KnowledgeExplorer from './pages/KnowledgeExplorer'
import SettingsPage from './pages/Settings'
import type { Capabilities } from './types'

type Tab = 'home' | 'ciclope' | 'argus' | 'compare' | 'knowledge' | 'settings'

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
          <button className={tab === 'compare' ? 'active' : ''} onClick={() => setTab('compare')}>
            Comparar
          </button>
          <button className={tab === 'knowledge' ? 'active' : ''} onClick={() => setTab('knowledge')}>
            Conhecimento
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
      {/* Páginas ficam SEMPRE montadas (só alternam visibilidade) para preservar a análise
          ao trocar de aba — permite ir e voltar comparando Cíclope × ARGUS sem perder o resultado. */}
      <div style={{ display: tab === 'home' ? 'block' : 'none' }}>
        <Home caps={caps} onNavigate={setTab} />
      </div>
      <div style={{ display: tab === 'ciclope' ? 'block' : 'none' }}>
        <Ciclope rate={caps?.usd_brl_rate ?? 6} factor={caps?.cost_factor ?? 1} />
      </div>
      <div style={{ display: tab === 'argus' ? 'block' : 'none' }}>
        <Argus caps={caps} />
      </div>
      <div style={{ display: tab === 'compare' ? 'block' : 'none' }}>
        <Compare caps={caps} />
      </div>
      <div style={{ display: tab === 'knowledge' ? 'block' : 'none' }}>
        <KnowledgeExplorer />
      </div>
      <div style={{ display: tab === 'settings' ? 'block' : 'none' }}>
        <SettingsPage />
      </div>
    </div>
  )
}
