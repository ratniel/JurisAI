# Agentic Pipeline Progress

## Goal

Build a retrieval-first agentic pipeline for JurisAI that:

- uses deterministic orchestration wherever possible
- minimizes LLM calls outside classification and response generation
- preserves a stable reference back to the original MongoDB scheme document
- can be tested end-to-end on the local `test_schemes` subset before scaling up

## Current Structural Decisions

### Retrieval representation

- We are using two vectors per scheme document.
- `Embedding A` is `name + details`.
- `Embedding B` is `eligibility + benefits`.
- Both vectors live in the same Qdrant collection as separate points.
- Both vectors must carry a Mongo reference in payload metadata so retrieval results can be cited in agent responses.
- We are not adding `faq` as a third embedding source in this phase.

### Metadata contract

Every Qdrant point should include:

- `mongo_ref.database`
- `mongo_ref.collection`
- `mongo_ref.document_id`
- `mongo_ref.url`
- `scheme_id`
- `embedding_profile`
- `embedded_fields`
- retrieval-friendly scheme metadata such as `name`, `level`, `provider`, and `tags`

### Field strategy

- `Embedding A`
  - fields: `name`, `details`
  - job: identify what the scheme is about
  - best for: discovery queries, topical matching, scheme naming
- `Embedding B`
  - fields: `eligibility`, `benefits`
  - job: identify who qualifies and what they receive
  - best for: user-fit queries, scholarship/assistance intent, benefit matching
- Deferred for metadata or later chunking:
  - `application_process`
  - `documents_required`
  - `faq`
  - these are better introduced after base retrieval is stable

### Local-first validation

- We are validating the pipeline first with local MongoDB and local Qdrant from Docker.
- We are using `test_schemes` as the initial source collection.
- We now have a separate derived Mongo collection `test_schemes_enriched` for processed test data.
- We are starting with local embeddings for faster iteration and cheaper debugging.

## Implemented

- Added a dual-profile Qdrant indexer in [scripts/index_schemes_in_qdrant.py](/Users/ratniel/JurisAI/scripts/index_schemes_in_qdrant.py).
- The indexer reads directly from any Mongo collection instead of being tied to Beanie's `schemes` collection.
- The indexer creates one point for `embedding_a` and one point for `embedding_b` for each Mongo scheme document.
- The payload for both vectors now contains a Mongo reference contract that can be used later for response citations.
- Added a query validation script in [scripts/query_qdrant_schemes.py](/Users/ratniel/JurisAI/scripts/query_qdrant_schemes.py) to test semantic retrieval and inspect Mongo references in returned hits.
- Added a metadata enrichment script in [scripts/enrich_scheme_metadata.py](/Users/ratniel/JurisAI/scripts/enrich_scheme_metadata.py) to derive normalized provider, channel, and FAQ fields for Mongo documents.
- Promoted enriched metadata fields into Qdrant payloads for indexed points:
  - `provider_type`
  - `state`
  - `ministry`
  - `application_modes`
- Added retrieval utilities in `src/retrieval/`:
  - deterministic filter mapping
  - dual-profile Qdrant search
  - result dedupe by Mongo-backed `scheme_id`
- Replaced the workflow retrieval stub with an actual retrieval execution step.

## In Progress

- Running the first insertion from `jurisai.test_schemes` into a dedicated Qdrant collection.
- Testing whether semantic search retrieves the expected scheme records with the new payload shape.
- Checking where the current agentic workflow stops short of actual retrieval execution.

## Validation Log

### 2026-03-14 local test run

- Indexed `jurisai.test_schemes` into Qdrant collection `test_schemes_vectors`.
- Result: `25` Mongo documents became `50` Qdrant points.
- Each scheme now contributes:
  - `embedding_a` for `name + details`
  - `embedding_b` for `eligibility + benefits`
- Both points include `mongo_ref.database`, `mongo_ref.collection`, `mongo_ref.document_id`, and `mongo_ref.url`.

### Query checks

- Query: `general loan scheme for backward classes`
  - Best hit: `NBCFDC General Loan Scheme`
  - Profile: `embedding_a`
- Query: `scholarship for disabled students`
  - Best hit: `Top Class Education For Students With Disabilities`
  - Profile: `embedding_b`
- Result summary:
  - semantic retrieval is functioning
  - profile-specific querying is already useful
  - payload references are present and ready for answer citations

### Agent workflow check

- The current workflow correctly classifies a scheme request and produces a retrieval plan.
- It does not yet execute the Qdrant lookup.
- Current stopping point: the workflow emits `call_scheme_retrieval` and returns the tool payload instead of retrieving schemes and generating an answer from results.

### Data inspection notes from `test_schemes`

- `provider` is highly normalizable:
  - all `state` records in the test subset use plain state names such as `Maharashtra`, `Gujarat`, `Madhya Pradesh`, and `Uttarakhand`
  - all `central` records use ministry-style providers such as `Ministry Of Social Justice and Empowerment`
- `application_process` has strong channel markers:
  - many entries start with `Online`, `Offline`, or both
  - these can be extracted into `application_modes.online` and `application_modes.offline`
- `application_process` often includes actionable contact data:
  - official URLs appear in many records
  - phone or helpline numbers appear in some records
- `documents_required` is parseable:
  - some records use numbered lists
  - others use sentence-style item lists separated by periods
- `eligibility` and `benefits` contain repeated numeric patterns:
  - income ceilings
  - scholarship or subsidy amounts
  - age conditions
  - tenure, percentage, or quota-style limits
- `faq` text and `sources` are consistently present in the test subset and can support retrieval, answer grounding, or later chunking work.

### 2026-03-14 metadata enrichment check

- Ran metadata enrichment against `jurisai.test_schemes`.
- Stored fields:
  - `provider_type`
  - `state`
  - `ministry`
  - `application_modes`
  - `faq`
- Verification result:
  - `provider_type=ministry`: 13
  - `provider_type=state`: 12
  - `application_modes.online=True, offline=True`: 3
  - `application_modes.online=True, offline=False`: 14
  - `application_modes.online=False, offline=True`: 8
  - `faq` non-empty: 25
- Conclusion:
  - the chosen preprocessing works cleanly on the `test_schemes` subset
  - these fields are suitable to promote into Qdrant payload metadata in the next indexing pass
  - `faq` remains stored in Mongo as normalized source text, but is not being added as a new vector source right now

### 2026-03-14 derived collection update

- Added support for writing enriched documents into a new Mongo collection.
- Created `jurisai.test_schemes_enriched` from `jurisai.test_schemes`.
- Preferred collection roles are now:
  - raw source: `jurisai.schemes`
  - testing subset: `jurisai.test_schemes`
  - processed testing subset: `jurisai.test_schemes_enriched`
  - test vectors: `test_schemes_vectors`

### 2026-03-24 raw and enriched contract split

- We now maintain two reusable scheme contracts:
  - raw scraped scheme data
  - enriched scheme data
- Raw documents keep `application_process` because it is the source text used for downstream transformations.
- Enriched documents remove `application_process` and carry `application_modes.online` and `application_modes.offline` as the retained application-detail fields.
- FAQ scraping now writes a single plain-text `faq` field directly instead of storing FAQ mappings and flattening them later.
- The raw-to-enriched pipeline is wired for `test_schemes -> test_schemes_enriched` first; full-dataset promotion remains a separate follow-up task.

### 2026-03-14 workflow retrieval integration check

- Added a live retrieval step to the workflow.
- The workflow now:
  - classifies intent
  - builds deterministic filters
  - queries Qdrant
  - dedupes scheme hits
  - passes grounded scheme data into response generation
- Verified case:
  - user request: `I need an offline Maharashtra disability award scheme`
  - applied filters: `state=Maharashtra`, `application_mode=offline`
  - top grounded result: `The Scheme Of State Award For Disabled`
  - response now includes a grounded answer plus a reference URL
- Current limitation:
  - unsupported classifier filters such as `target_group=disabled students` are still ignored until we add richer metadata extraction or filter mapping for target groups

## Next Planned Work

1. Improve ranking quality when classifier filters are only partially supported.
2. Add richer deterministic filters for target groups, category tags, age, and income.
3. Add reranking and confidence thresholds.
4. Decide how many retrieved schemes to pass into the answer prompt by default.
5. Promote the same flow from `test_schemes_vectors` to the full `schemes` dataset after validation.

## Candidate Preprocessing

### Easy and high-value

- Extract `provider_type`
  - values: `state`, `ministry`, `other`
- Extract `state`
  - for state-level schemes, derive from `provider`
- Extract `ministry`
  - for central schemes, derive from `provider`
- Extract `application_modes`
  - booleans for `online` and `offline`
- Extract `application_urls`
  - collect official links from `application_process`
- Extract `contact_numbers`
  - collect helpline or office phone numbers from `application_process`
- Parse `documents_required_list`
  - normalize numbered and sentence-style lists into arrays
- Keep `faq` as plain text
  - join question-answer pairs into one retrieval-friendly text field
  - for late chunking, question-answer pairs should eventually be emitted as chunkable text units rather than queried as a raw dict

### Easy and useful for filters

- Extract `income_ceiling`
  - from `eligibility`
- Extract `benefit_amounts`
  - from `benefits`
- Extract `age_min` and `age_max`
  - from `eligibility`
- Extract `scheme_type`
  - examples: `loan`, `scholarship`, `subsidy`, `pension`, `award`, `grant`
- Extract `target_groups`
  - examples: `students`, `disabled`, `women`, `farmers`, `artists`, `fishermen`

### Slightly later

- Extract `application_step_count`
  - useful for procedural complexity or UI summarization
- Extract `requires_office_visit`
  - infer from phrases like `visit district office`, `submit hard copy`, or `apply online`
- Extract `benefit_frequency`
  - one-time, monthly, quarterly, annual

## Step-By-Step Build Path

1. Lock the retrieval contract.
   - Keep the two-vector strategy as the default representation for each scheme.
   - Keep Mongo references mandatory in every Qdrant payload.

2. Validate indexing on the local test subset.
   - Use `jurisai.test_schemes`.
   - Keep a dedicated Qdrant collection for test runs.

3. Implement a retrieval client module.
   - Embed the query.
   - Search Qdrant.
   - Optionally search one profile or both.
   - Dedupe by `scheme_id`.

4. Define deterministic filters from user profile.
   - Map profile fields such as state, category, target group, age, income, and gender into metadata filters.
   - Do this without an extra LLM call.

5. Add workflow retrieval execution.
   - Replace the current `plan_tool_call` stop with an actual retrieval step.
   - Return top candidates plus Mongo references into workflow state.

6. Generate grounded answers.
   - Pass retrieved scheme summaries and `mongo_ref` payloads into the response generator.
   - Require the response to cite the originating scheme records.

7. Add quality control.
   - Add score thresholds.
   - Add reranking if needed.
   - Add a single retry path only when confidence is low.

8. Enrich index-time metadata.
   - Extract structured values for `state`, `category_tags`, `gender_target`, `age_range`, and `income_ceiling`.
   - Store them in payloads for filtering and explanation.

9. Expand retrieval coverage.
   - Add raw `application_process`, `documents_required`, and `faq` either as new profiles or as chunked secondary retrieval units.

10. Scale from `test_schemes` to `schemes`.
   - Keep the same payload contract and retrieval flow.
   - Re-run validation before switching the main collection.

## Preferences And Guardrails

- Prefer deterministic rule-based retrieval plumbing over additional LLM calls.
- Keep retrieval explainable: each result should map cleanly back to a Mongo document.
- Use the smallest viable dataset and infrastructure path first, then scale to the full schemes collection.
- Keep this document updated as implementation decisions change.

## Known Gap

The current workflow in [src/agentic/workflow.py](/Users/ratniel/JurisAI/src/agentic/workflow.py) still stops at tool selection for retrieval turns. It does not yet execute Qdrant search, rerank results, or pass scheme references into the answer generator.
