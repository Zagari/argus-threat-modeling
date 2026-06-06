import { useEffect, useState } from 'react'
import { getSettings } from './api/client'
import Analyze from './pages/Analyze'
import Detect from './pages/Detect'
import SettingsPage from './pages/Settings'

type Tab = 'analyze' | 'detect' | 'settings'

export default function App() {
  const [tab, setTab] = useState<Tab>('analyze')
  const [mock, setMock] = useState(false)

  useEffect(() => {
    getSettings()
      .then((s) => setMock(s.mock))
      .catch(() => {})
  }, [tab])

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>ARGUS &amp; Cíclope</h1>
          <div className="sub">Modelagem de ameaças STRIDE a partir de diagramas de arquitetura</div>
        </div>
        <nav className="tabs">
          <button className={tab === 'analyze' ? 'active' : ''} onClick={() => setTab('analyze')}>
            Analisar
          </button>
          <button className={tab === 'detect' ? 'active' : ''} onClick={() => setTab('detect')}>
            Detector (E1)
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
      {tab === 'analyze' && <Analyze />}
      {tab === 'detect' && <Detect />}
      {tab === 'settings' && <SettingsPage />}
    </div>
  )
}
