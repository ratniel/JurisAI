# Topic Taxonomy Experiment

This experiment keeps topic enrichment rule-based and fast.

## Current Decision

- We are enriching schemes with a `topics` field first.
- We are intentionally parking `eligibility_entities` for a later pass.
- The mapper is deterministic: no LLM calls, no embeddings, no regex-heavy eligibility parsing.
- The first validation target is MongoDB collection `test_schemes`.
- We are keeping `SC`, `ST`, `OBC`, `EWS`, `VJNT`, and similar beneficiary markers separate instead of collapsing them into `Social Welfare`.
- We are working with the full 25-topic list for now.
- Scheme-brand and commemorative tags stay intentionally unmapped unless they contain sector information.
- Broad benefit-only tags such as `Loan`, `Subsidy`, `Grant`, `Insurance`, `Allowance`, and `Pension` stay out of `topics`.
- Broad support words such as `Empowerment`, `Financial Assistance`, and `Welfare` stay out of `topics` unless another tag gives real sector context.

## Controlled Topics

The earlier discussion said "22 topics", but the explicit list actually contains 25 labels. This document keeps the explicit labels intact for now rather than collapsing categories without approval.

- Agriculture
- Animal Husbandry
- Fisheries
- Horticulture
- Rural Development
- Urban Development
- Housing
- Infrastructure
- Education
- Skill Development
- Employment
- Entrepreneurship
- Healthcare
- Nutrition
- Women Welfare
- Child Welfare
- Social Welfare
- Disability Support
- Senior Citizens
- Financial Inclusion
- Environment
- Energy
- Science & Research
- Sports
- Culture

## Rule Design Principles

- `tags` remain the raw source signal.
- `topics` are derived deterministically from tags.
- A tag may map to multiple topics when that is intuitive.
- A tag may map to no topic when it is only a beneficiary marker, only a benefit-type marker, or too scheme-specific to classify safely.

## Expected Edge-Case Buckets

- Beneficiary-only tags:
  `OBC`, `Scheduled Tribe`, `EWS`, `Minority`, `VJNT`
- Benefit-only tags:
  `Loan`, `Subsidy`, `Grant`, `Insurance`, `Allowance`
- Institution or brand tags:
  `AICTE`, `BIRAC`, `Atal`, `Maulana Azad`
- Generic support tags:
  `Assistance`, `Benefits`, `Coverage`, `Capital`
- Proper nouns and commemorative labels:
  personal names, memorial labels, scheme-brand labels

## Current Tooling

- Reusable topic rules live in [topic_taxonomy.py](/Users/ratniel/JurisAI/src/data_ingestion/topic_taxonomy.py).
- The enrichment runner lives in [map_scheme_topics.py](/Users/ratniel/JurisAI/scripts/map_scheme_topics.py).
- Generated experiment reports are written under `reports/topic_mapping_experiment/`.

## Open Questions For Later

- Do we want a separate `beneficiaries` enrichment pass next?
- Do we want a separate `benefit_types` enrichment pass next?
- Should `application_modes` eventually preserve line breaks instead of normalized single-line text?
