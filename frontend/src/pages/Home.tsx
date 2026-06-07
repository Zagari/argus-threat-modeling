import type { Capabilities } from '../types'

type Tab = 'home' | 'ciclope' | 'argus' | 'settings'

const STAGES: { id: string; name: string; desc: string; done: boolean }[] = [
  { id: 'E1', name: 'Detecção (YOLO11)', desc: 'detector supervisionado localiza os ícones/componentes no diagrama.', done: true },
  { id: 'E2', name: 'Leitura & Topologia', desc: 'OCR + fusão ícone↔rótulo, cross-check e topologia por VLM.', done: true },
  { id: 'E3', name: 'DFD', desc: 'monta o Data Flow Diagram e marca as fronteiras de confiança.', done: true },
  { id: 'E4', name: 'STRIDE-per-element', desc: 'ameaças por elemento, restritas à matriz STRIDE canônica.', done: true },
  { id: 'E5', name: 'Graph-RAG ancorado', desc: 'enriquece cada ameaça com CWE/CAPEC/ATT&CK/CVE (Neo4j + RAG).', done: false },
  { id: 'E6', name: 'DREAD + relatório', desc: 'pontuação de risco DREAD e relatório final auditável.', done: false },
]

export default function Home({ caps, onNavigate }: { caps: Capabilities | null; onNavigate: (t: Tab) => void }) {
  const argusMl = caps?.argus_ml ?? false
  const mock = caps?.llm.mock ?? false

  return (
    <div className="full">
      <div className="card hero-card">
        <h2 style={{ margin: '0 0 6px' }}>Modelagem de ameaças STRIDE a partir de diagramas de arquitetura</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Dois sistemas analisam a <strong>imagem de um diagrama</strong> (AWS/Azure/GCP, agnóstico) e produzem um
          modelo de ameaças <strong>STRIDE</strong> com cenários de ataque e contramedidas. Cada um tem a sua aba —
          o objetivo do projeto é <em>compará-los</em>.
        </p>
        <div className="chips">
          <span className={`chip ${argusMl ? 'ok' : 'off'}`}>
            ARGUS: {argusMl ? 'disponível neste ambiente ✓' : 'indisponível (modo LITE)'}
          </span>
          {caps && (
            <span className="chip">
              LLM: {caps.llm.provider}/{caps.llm.model}
            </span>
          )}
          <span className={`chip ${mock ? 'warn' : 'ok'}`}>{mock ? 'mock ligado' : 'análise real'}</span>
        </div>
      </div>

      <div className="systems">
        <div className="card system-card">
          <div className="system-head">
            <h3 style={{ margin: 0 }}>Cíclope</h3>
            <span className="badge cat">baseline · LLM-only</span>
          </div>
          <p className="muted">
            O “olho único”: a imagem vai <strong>direto a um VLM</strong>, que numa única passagem extrai
            componentes, conexões e ameaças STRIDE. É o <strong>melhor baseline possível</strong> (prompt sofisticado
            + saída estruturada), para uma comparação justa — não uma versão enfraquecida.
          </p>
          <ul className="feat">
            <li>Rápido (~30 s) e leve — não exige GPU/ML.</li>
            <li>Saída no mesmo contrato do ARGUS (<code>ThreatModel</code>), o que torna a comparação direta.</li>
          </ul>
          <button className="primary" onClick={() => onNavigate('ciclope')}>
            Abrir o Cíclope →
          </button>
        </div>

        <div className="card system-card">
          <div className="system-head">
            <h3 style={{ margin: 0 }}>ARGUS</h3>
            <span className="badge cat">especialista · pipeline E1–E6</span>
          </div>
          <p className="muted">
            Sistema especialista, <strong>auditável estágio a estágio</strong>. Em vez de uma caixa-preta, cada etapa
            expõe seu resultado parcial — você vê o “raciocínio” do pipeline:
          </p>
          <ul className="stages">
            {STAGES.map((s) => (
              <li key={s.id} className={s.done ? 'st-done' : 'st-todo'}>
                <span className="st-id">{s.id}</span>
                <span className="st-name">{s.name}</span>
                <span className="st-desc">{s.desc}</span>
                {!s.done && <span className="st-tag">em desenvolvimento</span>}
              </li>
            ))}
          </ul>
          <button className="primary" disabled={!argusMl} onClick={() => onNavigate('argus')}>
            {argusMl ? 'Abrir o ARGUS →' : 'ARGUS indisponível (LITE)'}
          </button>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Configurações</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Na aba <button className="linklike" onClick={() => onNavigate('settings')}>Configurações</button> você troca,
          em tempo de execução: o <strong>provedor de LLM</strong> (Gemini, Anthropic, OpenAI), o <strong>modelo</strong>,
          a <strong>temperatura</strong> e a <strong>chave de API</strong>; e liga/desliga o <strong>modo mock</strong>
          (resultado de exemplo, sem chamada real). A chave fica só em memória no servidor.
        </p>
      </div>
    </div>
  )
}
