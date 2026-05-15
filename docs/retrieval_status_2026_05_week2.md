# Retrieval Status: 2026 May Week 2

Date: 2026-05-14
Status: Focused experiment snapshot
Scope: `p1_vidarbha_farmer` and `p2_tamilnadu_sc_student` on the Nomic v2 eval subset

## 2026-05-15 Iteration

Status: Filter-policy sweep completed on the same six focused records after rebuilding the Nomic v2 collection with lowercase topic payloads and pinning query-time embeddings explicitly to `nomic-ai/nomic-embed-text-v1.5`.

New artifacts:

- retrieval-core:
  - `evals/retrieval/runs/retrieval_eval_20260515T122011Z_all.json`
  - `evals/retrieval/runs/retrieval_eval_20260515T122011Z_state_only.json`
  - `evals/retrieval/runs/retrieval_eval_20260515T122011Z_topics_only.json`
  - `evals/retrieval/runs/retrieval_eval_20260515T122011Z_state_hard_topics_soft.json`
- agentic-workflow:
  - `evals/agentic_workflow/runs/agentic_workflow_eval_20260515T122011Z_state_only.json`
  - `evals/agentic_workflow/runs/agentic_workflow_eval_20260515T122011Z_state_hard_topics_soft.json`

### Retrieval-core comparison

- `all`
  - `Recall@5`: `0.694`
  - `MRR@5`: `0.750`
  - `Distractor pass rate`: `0.167`
  - `Strict pass rate`: `0.000`
- `state_only`
  - `Recall@5`: `0.806`
  - `MRR@5`: `0.708`
  - `Distractor pass rate`: `0.333`
  - `Strict pass rate`: `0.333`
- `topics_only`
  - `Recall@5`: `0.528`
  - `MRR@5`: `0.617`
  - `Distractor pass rate`: `0.333`
  - `Strict pass rate`: `0.167`
- `state_hard_topics_soft`
  - `Recall@5`: `0.806`
  - `MRR@5`: `0.833`
  - `Distractor pass rate`: `0.167`
  - `Strict pass rate`: `0.167`

Readout:

- The stale topic-casing blocker is resolved. Hard topic filters no longer collapse to zero raw hits on this collection.
- `state_only` is the best current hard-filter policy on strict retrieval quality for this six-record slice.
- `topics_only` underperforms `state_only` even after fixing casing, so topic gating alone is too brittle.
- `state_hard_topics_soft` improves rank order for the Tamil Nadu engineering scholarship case, but it does not solve the Vidarbha wrong-beneficiary leakage because both the correct and incorrect Maharashtra farmer schemes share the `agriculture` topic.

### Topic-mapping correction found during the sweep

- A real failure mode was confirmed for explicit `engineering` topics.
- The prior taxonomy mapped `engineering -> science & research` only.
- That mapping was broadened to `education + science & research`, which improved the Tamil Nadu engineering scholarship case by allowing education-coded scholarship records to stay in play when the classifier emits an engineering-flavored topic.

### Agentic-workflow comparison

- `state_only`
  - `Recall@5`: `0.806`
  - `MRR@5`: `0.708`
  - `Distractor pass rate`: `0.333`
  - `Expected filter match rate`: `0.833`
  - `Zero raw hit rate`: `0.000`
  - `Classifier / workflow errors`: `0`
- `state_hard_topics_soft`
  - `Recall@5`: `0.444`
  - `MRR@5`: `0.417`
  - `Distractor pass rate`: `0.500`
  - `Expected filter match rate`: `0.500`
  - `Zero raw hit rate`: `0.500`
  - `Classifier / workflow errors`: `3`

Important caveat:

- The `state_hard_topics_soft` agentic run is confounded by Gemini rate-limit failures on `retrieval_eval_002`, `retrieval_eval_005`, and `retrieval_eval_006`.
- Because of those `429 RESOURCE_EXHAUSTED` failures, `state_hard_topics_soft` is not a fair end-to-end winner today even though it looked promising in retrieval-core ranking.

### Current Retrieval Decision

Use next:

1. keep `state_only` as the active retrieval policy and default operating mode for the next end-to-end agentic pass on this subset
2. keep the new shared `retrieval_filter_mode` controls for `all`, `state_only`, `topics_only`, and `state_hard_topics_soft`
3. keep explicit query-time embedding overrides visible in the harness when evaluating a non-default vector collection such as the Nomic subset
4. move the next retrieval-quality effort from topic policy into beneficiary-aware precision

Most important remaining failure:

- `p1_vidarbha_farmer` still leaks the same-state wrong-beneficiary scheme `Mahila Kisan Yojana (Maharashtra)`
- `state` and `topics` cannot separate that distractor because it shares the same state and broad agriculture topic
- the next meaningful gain is likely to come from stronger beneficiary signals such as:
  - soft tag or target-group scoring
  - better use of `fit_query`
  - planner or classifier extraction of durable beneficiary facts

## Snapshot

- A valid Nomic experiment required overriding both the active eval collection and the query-time embedding model:
  - collection: `eval_persona_schemes_vectors_v2_nomic_embed_text_v1_5`
  - query embedding model: `nomic-ai/nomic-embed-text-v1.5`
  - intent provider/model: `gemini` + `models/gemini-flash-lite-latest`
- The default eval path in this workspace was still pointed at the older MiniLM collection `eval_persona_schemes_vectors_v1`, so that path was not a valid Nomic measurement.
- The focused Nomic run did not show improvement under the current retrieval pipeline.
- The main failure pattern is not yet strong evidence against the `discovery_query` and `fit_query` split itself.
- The dominant blocker is a hard topic-filter mismatch that collapses result sets before vector similarity can do useful work.
- A maintained retrieval-filter flag now exists so the same eval path can be run with hard metadata filters enabled or disabled.

## Setup State

- Focused eval artifact:
  - `evals/retrieval/runs/retrieval_eval_20260514T140918Z.json`
- Unfiltered retrieval-core artifact:
  - `evals/retrieval/runs/retrieval_eval_20260514T143840Z.json`
- Unfiltered agentic-workflow artifact:
  - `evals/agentic_workflow/runs/agentic_workflow_eval_20260514T143840Z.json`
- Records evaluated:
  - `retrieval_eval_001`
  - `retrieval_eval_002`
  - `retrieval_eval_003`
  - `retrieval_eval_004`
  - `retrieval_eval_005`
  - `retrieval_eval_006`
- Qdrant collection:
  - `eval_persona_schemes_vectors_v2_nomic_embed_text_v1_5`
- Collection properties:
  - `100` points
  - vector size `768`
  - distance `Cosine`
- Local setup note:
  - running `nomic-ai/nomic-embed-text-v1.5` through the local sentence-transformer path required adding `einops` to the Python environment

## Focused Eval Snapshot

Artifact:

- `evals/retrieval/runs/retrieval_eval_20260514T140918Z.json`

Metrics across the six focused records:

- `Recall@5`: `0.056`
- `MRR@5`: `0.083`
- `Distractor pass rate`: `1.000`
- `Expected filter match rate`: `0.833`
- `Zero raw hit rate`: `0.833`
- `Strict pass rate`: `0.000`

## Second Experiment: Filters Off

Runtime mode:

- `retrieval_filters_enabled = false`
- collection: `eval_persona_schemes_vectors_v2_nomic_embed_text_v1_5`
- query embedding model: `nomic-ai/nomic-embed-text-v1.5`
- intent model: `models/gemini-flash-lite-latest`

### Retrieval-core result

Artifact:

- `evals/retrieval/runs/retrieval_eval_20260514T143840Z.json`

Metrics across the same six focused records:

- `Recall@5`: `0.583`
- `MRR@5`: `0.533`
- `Distractor pass rate`: `0.500`
- `Expected filter match rate`: `0.833`
- `Zero raw hit rate`: `0.000`
- `Strict pass rate`: `0.167`

Directional comparison against the filtered Nomic run:

- `Recall@5`: `0.056 -> 0.583`
- `MRR@5`: `0.083 -> 0.533`
- `Zero raw hit rate`: `0.833 -> 0.000`

### Agentic-workflow result

Artifact:

- `evals/agentic_workflow/runs/agentic_workflow_eval_20260514T143840Z.json`

Metrics across the same six focused records:

- `Recall@5`: `0.361`
- `MRR@5`: `0.500`
- `Distractor pass rate`: `0.500`
- `Expected filter match rate`: `0.833`
- `Zero raw hit rate`: `0.167`
- `Strict pass rate`: `0.000`

Important details:

- the agentic run produced grounded final answers with the same unfiltered retrieval mode
- one record (`retrieval_eval_005`) hit a Gemini `503 UNAVAILABLE` spike and fell into the workflow failure path
- the workflow could verbally reject some wrong-state or wrong-eligibility schemes, but the retrieved sets were still noisy enough that strict retrieval quality failed

## Persona Readout

- `p1_vidarbha_farmer`
  - all three records produced `0` raw hits
  - all three records carried `state = Maharashtra` plus `topics = agriculture`
  - this means the hard filter path eliminated the result set before either vector profile could help
- `p2_tamilnadu_sc_student`
  - two of three records produced `0` raw hits
  - the only record that returned results was `retrieval_eval_006`, where the final normalized filters did not include a hard `topics` filter
  - that surviving record still retrieved only one of the three golden positives at top-5

## Sanity Check Against The Same Nomic Collection

Using the same Nomic query embedding model and the same Nomic collection, but dropping the hard topic filter:

- `p1` with `state = Maharashtra` only returned `10` raw hits
- the top two `p1` results were the exact golden positives:
  - `69a522c7e00a48eb32037c5f`
  - `69999ec7e00a48eb3203788e`
- `p2` with `state = Tamil Nadu` only returned `10` raw hits
- the top four `p2` results included the three expected positives for the main scholarship case:
  - `69a522c7e00a48eb32037c32`
  - `6999a822e00a48eb32037b80`
  - `6999a539e00a48eb32037a8d`

This makes the current failure mode much clearer:

- the collection can return useful Nomic hits for these cases
- the current hard topic filter path is preventing those hits from being seen
- once those filters are removed entirely, recall comes back but distractor leakage becomes the next dominant problem

## Active Filter Mismatch

Current behavior:

- query-time topic normalization emits lowercase topics such as `agriculture` and `education`
- the v2 Nomic collection payload topics are still title-cased, for example `Agriculture` and `Education`
- the Qdrant filter path applies the lowercase topic values as hard exact-match filters

Observed effect:

- `state + topics` searches for `p1` and `p2` collapse to zero raw hits
- `state-only` searches on the same collection remain healthy

## Earlier Retrieval Decision

Do next:

1. keep the new retrieval-filter toggle for controlled experiments
2. fix topic casing or stop using `topics` as a brittle exact-match hard filter on the Nomic v2 subset
3. test a middle path instead of choosing only between:
   - current hard state/topic filtering that collapses recall
   - fully unfiltered search that leaks wrong-state and wrong-beneficiary distractors
4. likely next experiment:
   - keep explicit `state` as a hard filter when present
   - treat `topics` as a soft ranking signal, not a hard gate
5. rerun the same focused six-record experiment after that change, then expand to the full 15-record eval

Do not conclude yet:

- do not call the `discovery_query` and `fit_query` split a win
- do not call it a loss either
- the filtered run is confounded by the topic-filter mismatch
- the unfiltered run proves the collection can recover recall, but it also shows that we still need some precision control
- the next question is not simply `filters on` vs `filters off`; it is which narrower filter policy gives us the best recall-precision balance on the Nomic v2 subset
