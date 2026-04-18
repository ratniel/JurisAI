# Retrieval Hardening Notes

## Why This Patch Set Exists

We hit a concrete retrieval failure where user constraints like `location=Maharashtra`, `demographic=minority`, and `occupation=student` were either dropped or not used strongly enough, which let out-of-state schemes surface as top matches.

This patch set hardens retrieval in four places:

- query understanding
- rule/filter normalization
- result ranking
- raw vs enriched hydration consistency

## Main Changes

### 1. Added a query-side intent model

New module:

- [src/retrieval/query_intent.py](/Users/ratniel/JurisAI/src/retrieval/query_intent.py)

New model:

- `RetrievalIntentProfile`

It stores:

- `raw_query`
- `normalized_query`
- normalized structured filters
- inferred `query_topics`
- inferred `query_tags`
- query terms and ignored filters

This makes retrieval intent explicit instead of depending only on a free-form classifier string plus loosely structured filters.

### 2. Normalized classifier/user filters before retrieval

Location aliases such as `location` and `geography` now map to `state`, and topic filters now validate against the controlled topic taxonomy.

Relevant files:

- [src/retrieval/query_intent.py](/Users/ratniel/JurisAI/src/retrieval/query_intent.py)
- [src/scheme_contracts.py](/Users/ratniel/JurisAI/src/scheme_contracts.py)

### 3. Made state filtering safer

When a user specifies a state without explicitly pinning `level`, retrieval now treats that as:

- matching state schemes
- or central schemes

instead of only exact state matches.

Relevant file:

- [src/retrieval/rule_engine.py](/Users/ratniel/JurisAI/src/retrieval/rule_engine.py)

### 4. Added topic-aware and constraint-aware reranking

After dedupe, retrieved schemes are reranked using:

- state match
- central fallback
- query tag overlap
- query topic overlap

This makes query intent matter even when the classifier did not emit perfect structured filters.

Relevant file:

- [src/retrieval/qdrant_search.py](/Users/ratniel/JurisAI/src/retrieval/qdrant_search.py)

### 5. Fixed hydration drift between raw and enriched data

If retrieval points back to a raw collection, hydration now prefers the enriched companion collection first. If only a raw document is available, it is transformed into enriched shape before building the chat-context scheme.

This prevents metadata regressions like:

- `provider_type` falling back to `other`
- `application_modes` losing signal
- `topics` disappearing

Relevant file:

- [src/agentic/workflow.py](/Users/ratniel/JurisAI/src/agentic/workflow.py)

### 6. Strengthened response grounding

The reply prompt now explicitly tells the model not to present a scheme as relevant when state or eligibility facts clearly contradict user constraints, and to say so plainly when important constraints were ignored or no grounded match exists.

Relevant file:

- [src/agentic/workflow.py](/Users/ratniel/JurisAI/src/agentic/workflow.py)

## Topics: What Was True Before

Before this patch set, `topics` were:

- generated deterministically from tags during enrichment
- stored on enriched scheme documents
- copied into Qdrant payload metadata
- filterable if a caller explicitly passed `topics`

But they were not doing enough actual work because they were not:

- part of the embedded text
- inferred on the query side as an intent model
- used in reranking

## Topics: How They Work Now

`topics` now matter in three distinct ways.

### Scheme-side structure

They are still generated from tags and stored on enriched documents.

### Query-side intent

`RetrievalIntentProfile` now infers `query_topics` from the user request using the same controlled topic taxonomy.

This matches the original intent behind introducing topics: they are not just scheme metadata, they are also a structured way to represent user intent.

### Retrieval influence

They now affect retrieval through:

- explicit `topics` filters when the user/classifier provides them
- embedding text in the Qdrant index
- post-retrieval reranking via topic overlap

## Indexing Change

Qdrant embedding profiles were expanded so topic and metadata signals are part of the embedded text.

Updated profiles:

- `embedding_a`: discovery text plus `tags`, `topics`, and key scheme metadata
- `embedding_b`: fit text plus `tags`, `topics`, and key fit metadata

Relevant file:

- [scripts/index_schemes_in_qdrant.py](/Users/ratniel/JurisAI/scripts/index_schemes_in_qdrant.py)

Because of this change, test or production collections should be reindexed after deployment.

## Current Limitation

This patch set improves constraint handling a lot, but it does not fully solve beneficiary matching yet.

Example:

- `minority` is now preserved as query intent and used in normalized query/tag hints
- but we still do not have a dedicated extracted `target_groups` field on schemes

So beneficiary matching is better than before, but not yet as strong or deterministic as `state`, `level`, or `application_mode`.

## Recommended Next Steps

1. Build the retrieval eval set and score top-k results against golden schemes.
2. Expand deterministic target-group extraction beyond raw tags.
3. Improve topic/tag mapping coverage for currently unmapped tags.
4. Consider a second-stage rerank model once the labeled eval set exists.
