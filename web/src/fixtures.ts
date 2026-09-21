import type { ChatSessionRecord, TopSchemesArtifact } from './types'

const scheme = (n: number) => ({
  scheme_id: `fixture-${n}`,
  name: ['PM-KISAN', 'Pradhan Mantri Fasal Bima Yojana', 'Maharashtra Micro Irrigation Support', 'Kisan Credit Card'][n - 1] ?? `Sample Scheme ${n}`,
  url: 'https://www.myscheme.gov.in/',
  level: n === 3 ? 'state' : 'central',
  provider: n === 3 ? 'Maharashtra' : 'Government of India',
  details: 'Support for eligible applicants under the published scheme guidelines. Check the official source for current application steps and local availability.',
  eligibility: 'Eligibility depends on applicant category, location, and scheme requirements. Confirm current criteria on the official source.',
  benefits: 'May provide financial or service support to eligible households. Amounts and benefits can vary by location and current guidelines.',
  documents_required: 'Identity proof, address details, and supporting records may be requested. Confirm the exact list before applying.',
  retrieval_reason: 'Matches your location and the support you described.',
})

export function createFixtureSession(id: string): ChatSessionRecord {
  const now = new Date().toISOString()
  return { session_id: id, created_at: now, updated_at: now, session_snapshot: { user_profile: {}, preferences: {}, active_constraints: {}, recent_scheme_refs: [], relevant_schemes: [], latest_top_schemes_artifact: null }, messages: [], artifacts: [] }
}

export function createFixtureArtifact(sessionId: string): TopSchemesArtifact {
  return { artifact_id: 'fixture-artifact', artifact_type: 'top_schemes', chat_session_id: sessionId, turn_id: 'fixture-turn', schemes: Array.from({ length: 5 }, (_, i) => scheme(i + 1)) }
}

export const FIXTURE_ANSWER = `## Schemes that may be relevant\n\nBased on what you shared, these programs are a useful place to start. Eligibility depends on current scheme rules, your circumstances, and local availability.\n\n### What to do next\n1. Review each official scheme page.\n2. Confirm eligibility and required documents with the responsible department.\n3. Keep copies of application acknowledgements.\n\nThis guidance is informational. Check the official source before applying.`
