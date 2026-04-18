# Retrieval Status: 2026 April Week 1

## Snapshot

- State-derived filtering is fixed and working.
- When a state is known, the rule engine now derives schema-native vector filters:
  - `level = "state"`
  - `provider = "<state_name>"`
- The shared eval corpus, shared eval runner, and shared dashboard are all using the same retrieval path.
- Reranking is intentionally disabled. Current retrieval order is raw vector similarity after hard metadata filtering and scheme-level dedupe.

## Setup State

- MongoDB: up locally through `docker compose`
- Qdrant: up locally through `docker compose`
- Eval subset Mongo collection: `eval_persona_schemes_enriched_v1`
- Eval vector collection: `eval_persona_schemes_vectors_v1`
- Eval subset size:
  - `50` enriched Mongo documents
  - `100` Qdrant points
- Embeddings:
  - `embedding_a`
  - `embedding_b`
- Vector config:
  - size `384`
  - distance `Cosine`

## Full Eval Snapshot

Artifact:

- `evals/retrieval/runs/retrieval_eval_20260404T221932Z.json`

Metrics:

- `Recall@3`: `0.378`
- `Recall@5`: `0.511`
- `MRR@5`: `0.456`
- `Distractor pass rate`: `0.667`
- `Expected filter match rate`: `0.533`
- `Zero raw hit rate`: `0.067`
- `Strict pass rate`: `0.200`

## Persona-Level Readout

- `p1_vidarbha_farmer`
  - state/provider filtering works
  - recall is strong
  - same-state wrong-beneficiary distractors still leak
- `p2_tamilnadu_sc_student`
  - geography and topic filtering work
  - hard `SC` tag filtering appears too restrictive and hurts recall
- `p3_rajasthan_widow_support`
  - state filtering works
  - `Women Welfare` topic intent is not being predicted strongly enough
- `p4_central_pwd_support`
  - central-first intent is not being normalized into a strong enough hard filter
  - `Disability Support` is not consistently making it into hard retrieval filters
- `p5_northeast_st_microbusiness`
  - Assam plus beneficiary hard filtering is brittle
  - one record produced zero raw hits

## Current First-Pass Filter Policy

There are two filter stages before ranking by vector score:

### 1. Intent normalization

Implemented in:

- `src/retrieval/query_intent.py`

This stage can populate or infer the canonical retrieval filter fields:

- `state`
- `level`
- `provider`
- `provider_type`
- `ministry`
- `application_mode`
- `online`
- `offline`
- `tags`
- `topics`

This stage also produces soft query-side signals:

- `query_topics`
- `query_tags`
- `query_terms`

Important note:

- some user-profile concepts like `demographic`, `occupation`, `community`, and `category`
  are not real schema fields
- they are currently translated into query hints and may still indirectly become `tags` or `topics`

### 2. Hard Qdrant metadata filter construction

Implemented in:

- `src/retrieval/rule_engine.py`

Current hard-filterable fields are:

- `state`
- `level`
- `provider`
- `provider_type`
- `ministry`
- `application_mode`
- `online`
- `offline`
- `tags`
- `topics`

Important behavior:

- if `state` is present and `level/provider` are not explicit, retrieval uses:
  - state branch: `level="state"` and `provider="<state>"`
  - central fallback branch: `level="central"`
- this means yes, there are hard filters before vector similarity search
- those filters can absolutely restrict which schemes are even eligible to be retrieved

## Why This Does Not Look Like A Vector Infrastructure Problem

The infrastructure checks are healthy:

- Mongo data is present with the expected enriched fields
- Qdrant collection is green
- vector count and payload metadata are correct
- the p1 records prove that state extraction is reaching the vector DB correctly via `level/provider`

The failure pattern also points away from infra and toward retrieval policy:

- p1 fails by leaking same-state distractors, not by missing state filtering
- p2 and p5 fail in ways that suggest over-filtering
- p3 and p4 fail in ways that suggest weak topic/intent normalization
- only one record had zero raw hits, and that one had a very restrictive hard filter combination

So the main problem now is retrieval policy, not broken storage or indexing.

## Retrieval Query Note

The generated `retrieval_query` matters because it becomes the basis for:

- normalized query text
- embedding input
- query-side topic/tag/term augmentation

We have not yet done a disciplined pass on matching generated retrieval-query phrasing to the shape of the embedded text fields.

That should be a dedicated next-step investigation:

1. inspect the embedded field mixes for `embedding_a` and `embedding_b`
2. study the language pattern of `details`, `eligibility`, and `benefits`
3. decide whether retrieval queries should be rewritten into a more scheme-text-like style

## HyDE Note

HyDE-style retrieval or other query-expansion methods are parked for now.

Reason:

- current failures are still explainable through filter policy and query normalization
- adding synthetic query expansion before fixing hard-vs-soft filter behavior would make debugging harder

## Current Retrieval Decision

Do next:

- keep state-to-`level/provider` logic as is
- keep reranking disabled
- simplify first-pass hard filters
- stop turning beneficiary/category hints into brittle hard tag filters too early
- strengthen topic prediction for:
  - `Women Welfare`
  - `Disability Support`
  - `Entrepreneurship`
  - `Culture`
- add stronger handling for explicit central-first queries
- move retrieval strategy toward explicit tools instead of one fixed retrieval policy
- let the LLM/orchestrator decide how to fetch, when to filter, and how to answer after retrieval

Do not do next:

- do not add reranking back yet
- do not introduce persona-scoped retrieval shortcuts
- do not jump to HyDE or more advanced query expansion yet

## Tool-Based Retrieval Direction

The intended direction is to expose retrieval as a small set of explicit tools instead of
hard-coding one universal retrieval strategy.

Current preferred tool shapes:

- semantic search
- state-scoped search
- topic-scoped search

The long-term agentic goal is:

1. the LLM decides which retrieval tool to call
2. the LLM decides whether filters should be used
3. retrieval returns grounded schemes plus debug metadata
4. the same agentic workflow then generates the final answer from those grounded results

This means the power of the system should come from:

- reliable retrieval primitives
- explicit tool interfaces
- agent-level decision making

not from a growing set of hidden hard-coded retrieval heuristics.

## UI Requirement For Next Phase

Build a real-time evaluation and debugging UI for agentic retrieval runs.

The UI should support:

- run one persona or all personas
- run one record or a full persona slice
- show tool calls chosen by the LLM
- show tool inputs
- show tool outputs
- show intermediate retrieval state inline
- show classifier output
- show normalized query and filters
- show retrieved schemes grouped under the tool call that produced them
- show the final grounded answer generation
- show traces or structured debug metadata when available

The goal of this UI is to make agentic retrieval decisions inspectable end to end in one place.

## Planned Release Follow-Up

The next release-oriented context change should split the current chat state into three planes:

- `session_memory` for compact persistent user and conversation state
- `grounding_pack` for per-turn responder grounding
- `debug_trace` for Phoenix and operator inspection only

The product-facing addition should be a top-schemes artifact that:

- is created per turn
- can be shown directly in the UI
- exposes a compact prompt view to the LLM
- preserves fuller scheme details for user inspection

This should reduce prompt bloat without removing the current debug surface.

## Generation Status

The agentic workflow already has a generation step after retrieval in:

- `src/agentic/workflow.py`

The retrieval eval dashboard does not evaluate answer generation. It only evaluates retrieval quality.

So:

- `R` exists
- `G` exists in the workflow POC
- what is missing is answer-quality evaluation and tighter integration around grounded response quality
