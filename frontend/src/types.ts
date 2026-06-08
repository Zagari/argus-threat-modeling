export type StrideCategory =
  | 'Spoofing'
  | 'Tampering'
  | 'Repudiation'
  | 'Information Disclosure'
  | 'Denial of Service'
  | 'Elevation of Privilege'

export type ElementType = 'Process' | 'DataStore' | 'DataFlow' | 'ExternalEntity' | 'TrustBoundary'

export interface Mitigation {
  description: string
  type: string
  refs: string[]
}

export interface Threat {
  id: string
  component_id: string
  element_type: ElementType
  stride_category: StrideCategory
  title: string
  attack_scenario: string
  likelihood: string
  impact: string
  risk_score: number
  cwe_ids: string[]
  capec_ids: string[]
  attack_ids: string[]
  mitigations: Mitigation[]
  status: string
  provenance: string
  grounded: boolean
  dread?: Record<string, number> | null
  dread_score?: number | null
  dread_band?: string | null
}

export interface Component {
  id: string
  canonical: string
  label: string | null
  element_type: ElementType
  bbox: number[] | null
  confidence: number | null
  cve_ids?: string[]
}

export interface Cve {
  id: string
  cvss: number | null
  severity: string
  cpe: string
  url: string
  text?: string
}

export interface CveByComponent {
  component: string
  canonical: string
  label: string | null
  cves: Cve[]
}

export interface Edge {
  source: string
  target: string
  label: string | null
  crosses_boundary: boolean
}

export interface ThreatModel {
  system_name: string
  components: Component[]
  edges: Edge[]
  threats: Threat[]
  meta: Record<string, unknown>
}

export interface DetectionResult {
  components: Component[]
  annotated_image: string | null
  model: Record<string, unknown>
}

export interface DetectStatus {
  available: boolean
  weights?: string
  reason?: string
}

export interface Capabilities {
  version: string
  argus_ml: boolean
  llm: { provider: string; model: string; mock: boolean }
  usd_brl_rate: number
  cost_factor: number
}

export interface TextRegion {
  text: string
  bbox: number[]
  confidence: number | null
}

export interface Usage {
  calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_usd: number
  cost_known?: boolean
  mock?: boolean
}

// Payload de um evento SSE por estágio (campos variam conforme o estágio).
export interface StageEvent {
  system_name?: string
  components?: Component[]
  edges?: Edge[]
  threats?: Threat[]
  text_regions?: TextRegion[]
  annotated_image?: string | null
  model?: Record<string, unknown>
  summary?: Record<string, unknown>
  threat_model?: ThreatModel
  usage_delta?: Usage
  elapsed_s?: number
  latency_s?: number
  ocr_used?: boolean
  fused?: boolean
  crosscheck_used?: boolean
  added?: number
  n_text?: number
  n_labeled?: number
  n_edges?: number
  n_threats?: number
  // E5 (enriquecimento/groundedness + CVEs reais)
  groundedness?: number
  id_validity?: number
  grounded?: number
  ids_valid?: number
  ids_invalid?: number
  n_cves?: number
  cves?: CveByComponent[]
  // E6 (DREAD)
  dread_dist?: Record<string, number>
  status?: number
  message?: string
}

// ── Base de conhecimento (E5 / Knowledge Explorer) ──
export interface SubgraphNode {
  id: string
  kind: string
  name: string
  url: string | null
}
export interface SubgraphEdge {
  source: string
  target: string
  type: string
}
export interface Subgraph {
  canonical: string
  stride: string
  nodes: SubgraphNode[]
  edges: SubgraphEdge[]
}
export interface KnowledgeOptions {
  classes: string[]
  stride: string[]
}
export interface KnowledgeHit {
  id: string
  kind: string
  name: string
  url: string | null
}

export interface Settings {
  provider: string
  model: string
  temperature: number
  mock: boolean
  usd_brl_rate: number
  cost_factor: number
  has_key: boolean
  providers_with_key: string[]
  available_providers: string[]
  default_models: Record<string, string>
}
