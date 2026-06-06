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
}

export interface Component {
  id: string
  canonical: string
  label: string | null
  element_type: ElementType
  bbox: number[] | null
  confidence: number | null
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

export interface Settings {
  provider: string
  model: string
  temperature: number
  mock: boolean
  has_key: boolean
  providers_with_key: string[]
  available_providers: string[]
  default_models: Record<string, string>
}
