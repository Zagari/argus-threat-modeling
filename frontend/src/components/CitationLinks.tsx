import { Fragment } from 'react'

// Arquivo do capítulo ASVS 4.0.3 no GitHub (deep-link por capítulo).
const ASVS_CHAPTER_FILE: Record<string, string> = {
  V1: '0x10-V1-Architecture.md',
  V2: '0x11-V2-Authentication.md',
  V3: '0x12-V3-Session-management.md',
  V4: '0x12-V4-Access-Control.md',
  V5: '0x13-V5-Validation-Sanitization-Encoding.md',
  V6: '0x14-V6-Cryptography.md',
  V7: '0x15-V7-Error-Logging.md',
  V8: '0x16-V8-Data-Protection.md',
  V9: '0x17-V9-Communications.md',
  V10: '0x18-V10-Malicious.md',
  V11: '0x19-V11-BusLogic.md',
  V12: '0x20-V12-Files-Resources.md',
  V13: '0x21-V13-API.md',
  V14: '0x22-V14-Config.md',
}
const ASVS_PROJECT = 'https://owasp.org/www-project-application-security-verification-standard/'

/** URL oficial da fonte para um identificador de catálogo (CWE/CAPEC/ATT&CK/CVE/ASVS). */
export function urlForId(id: string): string | null {
  const s = id.trim().toUpperCase()
  let m: RegExpMatchArray | null
  if ((m = s.match(/^CWE-(\d+)$/))) return `https://cwe.mitre.org/data/definitions/${m[1]}.html`
  if ((m = s.match(/^CAPEC-(\d+)$/))) return `https://capec.mitre.org/data/definitions/${m[1]}.html`
  if (s.match(/^CVE-\d{4}-\d+$/)) return `https://nvd.nist.gov/vuln/detail/${s}`
  if ((m = s.match(/^(T\d{4})(?:\.(\d+))?$/)))
    return m[2] ? `https://attack.mitre.org/techniques/${m[1]}/${m[2]}/` : `https://attack.mitre.org/techniques/${m[1]}/`
  if ((m = s.match(/^ASVS-(V\d+)/))) {
    const file = ASVS_CHAPTER_FILE[m[1]]
    return file ? `https://github.com/OWASP/ASVS/blob/v4.0.3/4.0/en/${file}` : ASVS_PROJECT
  }
  if (s.startsWith('ASVS')) return ASVS_PROJECT
  return null
}

/** Renderiza uma lista de IDs como links clicáveis para a fonte (fallback: texto puro). */
export default function CitationLinks({ ids, sep = ', ' }: { ids: string[]; sep?: string }) {
  return (
    <>
      {ids.map((id, i) => {
        const url = urlForId(id)
        return (
          <Fragment key={`${id}-${i}`}>
            {i > 0 && sep}
            {url ? (
              <a className="cite" href={url} target="_blank" rel="noreferrer">
                {id}
              </a>
            ) : (
              id
            )}
          </Fragment>
        )
      })}
    </>
  )
}
