import { useState } from 'react'
import Analyze from './pages/Analyze'
import SettingsPage from './pages/Settings'

type Tab = 'analyze' | 'settings'

export default function App() {
  const [tab, setTab] = useState<Tab>('analyze')
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
          <button className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>
            Configurações
          </button>
        </nav>
      </header>
      {tab === 'analyze' ? <Analyze /> : <SettingsPage />}
    </div>
  )
}
