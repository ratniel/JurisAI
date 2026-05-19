import type { SchemeSource, TopSchemeArtifactEntry } from '../types'

export type SourceLink = {
  text?: string | null
  url: string
}

export function humanizeToken(value: string): string {
  return value
    .replace(/^['"]|['"]$/g, '')
    .split('_')
    .filter(Boolean)
    .join(' ')
}

export function buildSchemeSummary(scheme: TopSchemeArtifactEntry): string {
  return (
    firstLine(scheme.retrieval_reason) ??
    firstLine(scheme.benefits) ??
    firstLine(scheme.details) ??
    firstLine(scheme.eligibility) ??
    'Relevant scheme surfaced for your current context.'
  )
}

export function buildSchemeTags(scheme: TopSchemeArtifactEntry): string[] {
  const tags = [...(scheme.topics ?? []), ...(scheme.tags ?? []), scheme.state, scheme.level]
    .filter((tag): tag is string => Boolean(tag))
    .map((tag) => humanizeToken(tag))

  return Array.from(new Set(tags)).slice(0, 3)
}

export function getSourceLinks(sources?: SchemeSource[]): SourceLink[] {
  const unique = dedupeLinks(
    (sources ?? []).flatMap((source) =>
      source.url ? [{ text: source.text, url: source.url }] : [],
    ),
  )
  const official = unique.filter((source) => isPreferredOfficialUrl(source.url))
  return official.length ? official : unique
}

export function getPrimarySchemeUrl(scheme: TopSchemeArtifactEntry): string | null {
  const candidates = getDisplaySourceLinks(scheme)
  if (!candidates.length) {
    return null
  }

  const [bestLink] = [...candidates].sort(
    (left, right) => urlPriority(right.url) - urlPriority(left.url),
  )
  return bestLink?.url ?? null
}

export function getDisplaySourceLinks(scheme?: TopSchemeArtifactEntry | null): SourceLink[] {
  if (!scheme) {
    return []
  }

  return dedupeLinks([
    ...getSourceLinks(scheme.references),
    ...(scheme.url ? [{ text: scheme.name, url: scheme.url }] : []),
  ]).sort((left, right) => urlPriority(right.url) - urlPriority(left.url))
}

export function isPreferredOfficialUrl(url: string): boolean {
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    return (
      (hostname.endsWith('.gov.in') || hostname.endsWith('.nic.in')) &&
      !hostname.includes('myscheme.gov.in')
    )
  } catch {
    return false
  }
}

export function urlPriority(url: string): number {
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    if (isPreferredOfficialUrl(url)) {
      return 3
    }
    if (hostname.endsWith('.gov.in') || hostname.endsWith('.nic.in')) {
      return 2
    }
    if (hostname.includes('myscheme.gov.in')) {
      return 1
    }
  } catch {
    return 0
  }

  return 0
}

export function firstLine(value?: string | null): string | null {
  const trimmed = value?.trim()
  if (!trimmed) {
    return null
  }

  return trimmed.split('\n').find(Boolean)?.replace(/^[-*]\s*/, '') ?? trimmed
}

function dedupeLinks(links: SourceLink[]): SourceLink[] {
  const seen = new Set<string>()
  return links.filter((link) => {
    if (!link.url || seen.has(link.url)) {
      return false
    }

    seen.add(link.url)
    return true
  })
}
