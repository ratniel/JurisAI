# Retrieval Evaluation Plan

## Goal

Create a small but high-signal evaluation set that helps us improve retrieval quality with measurable pass/fail criteria.

Each evaluation row should preserve:

- the raw way a user would actually ask
- the normalized query text we embed
- the exhaustive set of schemes that must be retrieved

## Recommended Eval Row Shape

Use JSONL so each case is easy to diff and score.

```json
{
  "query_id": "eval_001",
  "user_query": "I'm a disabled student in Maharashtra. Is there any offline scholarship or award I can apply for?",
  "embed_query": {
    "discovery": "state Maharashtra disabled student scholarship award offline scheme education assistance",
    "fit": "disabled student in Maharashtra seeking offline scholarship or award education assistance"
  },
  "query_intent": {
    "query_topics": ["Education"],
    "query_tags": ["Student", "Person With Disability"]
  },
  "expected_filters": {
    "state": "Maharashtra",
    "application_mode": "offline"
  },
  "golden_retrieved_schemes": [
    {
      "scheme_id": "scheme-or-mongo-id",
      "name": "The Scheme Of State Award For Disabled"
    }
  ],
  "excluded_schemes": [],
  "notes": "Must retrieve disability-focused Maharashtra scheme even if query mixes scholarship and award language."
}
```

## How To Generate `embed_query`

Do not hand-author `embed_query` for every eval row. Generate it with the same deterministic logic we will use in production, then store the generated value in the dataset as a snapshot for regression tracking.

Recommended flow:

1. Keep `user_query` as the only human-written query field.
2. Run a deterministic normalization step that:
   - lowercases and trims filler
   - preserves geography, category, demographic, and application-mode cues
   - keeps benefit-intent words like `scholarship`, `loan`, `subsidy`, `award`, `pension`
   - keeps user-fit phrases like `disabled student`, `widow`, `farmer`, `senior citizen`
   - drops purely conversational text like `can you help me`, `please`, `I want to know`
3. Build profile-aware query strings from the normalized representation:
   - `discovery`: intent terms, scheme type, domain keywords, geography
   - `fit`: user attributes, benefit intent, geography, channel constraints
4. Store query-side intent separately when useful:
   - `query_topics` for controlled-domain intent such as `Education` or `Disability Support`
   - `query_tags` for beneficiary-style hints such as `Student` or `Minority Community`

This matches the current dual-profile index design better than a single shared query string.

## What Should Be Embedded

### Embed directly

These fields are high-signal for first-pass retrieval:

- `name`
- `details`
- `eligibility`
- `benefits`
- `tags`
- `topics`
- `provider`
- `provider_type`
- `state`
- `ministry`
- `level`
- `application_modes`
- `scheme_type` once extracted reliably
- selected normalized target-group labels once extracted reliably

### Keep as payload or deterministic filters

These should mostly support filtering, reranking, or UI display rather than first-pass embedding:

- `state`
- `level`
- `provider_type`
- `ministry`
- `application_modes`
- numeric fields such as income ceilings, age ranges, benefit amounts

Even when a field is filterable, it can still appear as a short text header inside the embedding document to improve semantic alignment.

## What Should Not Be First-Pass Embedded

Keep these out of the main dense embedding for now because they add procedural noise or are better handled on a narrowed candidate set:

- `faq`
- `documents_required`
- long procedural `application_process` text

## Recommended Embedding Profiles

### Discovery profile

Use:

- `name`
- `details`
- `tags`
- `topics`
- `provider`
- `provider_type`
- `state`
- `ministry`
- `level`
- `scheme_type`
- `application_modes`

Job:

- identify what the scheme is about
- improve match quality for noisy, colloquial, or underspecified user queries

### Fit profile

Use:

- `eligibility`
- `benefits`
- `target_groups`
- `scheme_type`
- `state`
- `level`
- `application_modes`
- selected normalized numeric hints if extraction is reliable

Job:

- identify whether the scheme fits the user's situation
- improve match quality for who-qualifies and what-do-I-get queries

## Late Chunking Note

After first-pass retrieval returns a small candidate set, run late chunking on:

- `benefits`
- `eligibility`
- `faq`

This keeps the full-dataset indexing cheaper and more stable, while still enabling focused follow-up responses on a selected scheme.

## UI Follow-Up Note

After the initial retrieval response, show a compact UI popup near chat for the top 3 retrieved schemes.

Clicking a scheme should trigger a short scheme-details answer backed by the late-chunked `benefits`, `eligibility`, and `faq` content for that specific scheme.
