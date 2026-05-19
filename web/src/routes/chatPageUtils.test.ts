import { describe, expect, it } from 'vitest'

import type { TopSchemeArtifactEntry } from '../types'
import {
  buildSchemeSummary,
  buildSchemeTags,
  getPrimarySchemeUrl,
  getSourceLinks,
} from './chatPageUtils'

describe('chatPageUtils', () => {
  it('prefers retrieval reason when building shortlist summaries', () => {
    const scheme: TopSchemeArtifactEntry = {
      scheme_id: 'scheme-1',
      retrieval_reason: 'Matched for women entrepreneurs in Maharashtra.',
      benefits: 'Fallback benefits text.',
      details: 'Fallback details text.',
      eligibility: 'Fallback eligibility text.',
    }

    expect(buildSchemeSummary(scheme)).toBe('Matched for women entrepreneurs in Maharashtra.')
  })

  it('uses topics before tags when building shortlist chips', () => {
    const scheme: TopSchemeArtifactEntry = {
      scheme_id: 'scheme-1',
      topics: ['Women Welfare', 'Entrepreneurship'],
      tags: ['Women', 'Loan'],
      state: 'Maharashtra',
      level: 'state',
    }

    expect(buildSchemeTags(scheme)).toEqual([
      'Women Welfare',
      'Entrepreneurship',
      'Women',
    ])
  })

  it('prefers official gov links over myscheme links', () => {
    const scheme: TopSchemeArtifactEntry = {
      scheme_id: 'scheme-1',
      name: 'Scheme One',
      url: 'https://www.myscheme.gov.in/schemes/scheme-one',
      references: [
        { text: 'myscheme', url: 'https://www.myscheme.gov.in/schemes/scheme-one' },
        { text: 'official', url: 'https://maharashtra.gov.in/scheme-one' },
      ],
    }

    expect(getSourceLinks(scheme.references)).toEqual([
      { text: 'official', url: 'https://maharashtra.gov.in/scheme-one' },
    ])
    expect(getPrimarySchemeUrl(scheme)).toBe('https://maharashtra.gov.in/scheme-one')
  })
})
