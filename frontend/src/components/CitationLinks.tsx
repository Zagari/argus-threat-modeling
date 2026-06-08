import { Fragment } from 'react'

/** URL oficial da fonte para um identificador de catálogo (CWE/CAPEC/ATT&CK/CVE/ASVS). */
export function urlForId(id: string): string | null {
  const s = id.trim().toUpperCase()
  let m: RegExpMatchArray | null
  if ((m = s.match(/^CWE-(\d+)$/))) return `https://cwe.mitre.org/data/definitions/${m[1]}.html`
  if ((m = s.match(/^CAPEC-(\d+)$/))) return `https://capec.mitre.org/data/definitions/${m[1]}.html`
  if (s.match(/^CVE-\d{4}-\d+$/)) return `https://nvd.nist.gov/vuln/detail/${s}`
  if ((m = s.match(/^(T\d{4})(?:\.(\d+))?$/)))
    return m[2] ? `https://attack.mitre.org/techniques/${m[1]}/${m[2]}/` : `https://attack.mitre.org/techniques/${m[1]}/`
  if (s.startsWith('ASVS')) return 'https://owasp.org/www-project-application-security-verification-standard/'
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
