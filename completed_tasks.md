# Completed Tasks

## 2026-05-15

- Removed the temporary `inspect_eval_run.py` helper and its doc mention to keep the retrieval harness surface clean.
- Added a shared `retrieval_filter_mode` path across retrieval-core eval, agentic-workflow eval, workflow retrieval, and the score scripts, covering:
  - `all`
  - `none`
  - `state_only`
  - `topics_only`
  - `state_hard_topics_soft`
- Added explicit query-embedding overrides to the eval runners and score scripts so Nomic collection experiments can pin `embedding_backend` and `embedding_model` instead of depending on the workspace default embedding config.
- Rebuilt `eval_persona_schemes_vectors_v2_nomic_embed_text_v1_5` from `eval_persona_schemes_enriched_v1`, restoring lowercase topic payloads in the Nomic v2 Qdrant subset.
- Added backward-compatible topic filter expansion so hard topic filters can still match older title-cased payload topics when needed.
- Confirmed through a focused six-record sweep that:
  - `state_only` is the strongest current strict retrieval policy on the Nomic subset
  - `topics_only` is not reliable enough to gate retrieval by itself
  - `state_hard_topics_soft` improves ranking for the Tamil Nadu engineering scholarship case but does not resolve the Vidarbha wrong-beneficiary leak
- Set `state_only` as the default retrieval filter mode in shared settings after the focused Nomic filter-policy sweep.
- Corrected the concrete topic-mapping failure `engineering -> science & research` by broadening it to `education + science & research`.
- Recorded the new filter-policy and Nomic-query-alignment results in [docs/retrieval_status_2026_05_week2.md](/Users/ratniel/JurisAI/docs/retrieval_status_2026_05_week2.md).

## 2026-05-14

- Verified that the default eval path in this workspace was still pointed at the older MiniLM subset collection `eval_persona_schemes_vectors_v1`, and identified the actual Nomic subset collection as `eval_persona_schemes_vectors_v2_nomic_embed_text_v1_5`.
- Added `einops` to the Python dependencies so the local `nomic-ai/nomic-embed-text-v1.5` sentence-transformer path can run inside the shared `uv` environment.
- Ran a focused Gemini intent eval on `retrieval_eval_001` through `retrieval_eval_006` against the Nomic v2 subset and recorded the results in [docs/retrieval_status_2026_05_week2.md](/Users/ratniel/JurisAI/docs/retrieval_status_2026_05_week2.md).
- Confirmed that the current Nomic zero-hit failures for the Vidarbha and Tamil Nadu student cases are dominated by a hard topic-filter mismatch, while state-only searches on the same collection recover the expected positive schemes.
- Added a maintained retrieval-filter flag across shared retrieval, retrieval-core eval, and agentic-workflow eval so the same setup can be run with hard metadata filters enabled or disabled.
- Ran the second focused Nomic experiment with `retrieval_filters_enabled = false` and recorded that retrieval recall recovered strongly, zero-hit failures disappeared in retrieval-core, and distractor leakage became the next dominant failure mode.

## 2026-05-05

- Split retrieval query handling so the live retrieval path can carry both a `discovery_query` for the `name + details` profile and a `fit_query` for the `eligibility + benefits` profile while keeping the old `retrieval_query` field as a compatibility bridge.
- Updated the classifier, retrieval planner, intent normalization, Qdrant search path, and eval artifacts so `embedding_a` and `embedding_b` no longer have to share the exact same embedded query text.

## 2026-05-01

- Added a new retrieval design note in [docs/retrieval_profile_and_corrective_loop_design_2026_05_01.md](/Users/ratniel/JurisAI/docs/retrieval_profile_and_corrective_loop_design_2026_05_01.md) to capture the next product direction for:
  - beneficiary-aware retrieval
  - corrective retrieval before final answer generation
  - agent-controlled structured follow-up UI
- Logged the intended split between durable user-profile facts and turn-specific situational facts so future retrieval work can use both without treating every beneficiary signal as free-form query text.
- Recorded that the next retrieval-quality phase should keep the Nomic v2 dual-profile baseline while shifting focus from more embedding experiments toward corrective retrieval policy and eligibility-aware follow-up.

## 2026-04-24

- Added a shared harness writing guide in `/Users/ratniel/JurisAI/docs/harness_document_guidelines.md` covering repo-root and surface-local `AGENTS.md`, skills, `TODO.md`, and `completed_tasks.md`.
- Recorded that harness documents should be updated alongside important project decisions and the code changes that implement them, rather than as delayed cleanup.

## 2026-04-19

- Reframed the active retrieval work as an explicit P0 track centered on three immediate fixes:
  - leaner v2 embedding profiles
  - retrieval-query generation experiments against golden records
  - lowercase topic normalization across retrieval metadata
- Updated repo tracking so the current source-of-truth docs now point at a new Qdrant collection/version for the next indexing pass instead of mutating the live vector setup blindly.
- Updated the retrieval planning and harness docs so future work compares retrieval-query formats and embedding models against exported golden-profile texts for the Vidarbha farmer query.
- Recorded that these are planning and documentation updates only; the v2 collection, re-index, and prompt/model experiments still need implementation.

## 2026-04-16

- Added a repo-root `bun run dev` launcher that starts the FastAPI chat API and the Vite frontend together for local development testing.
- Added `concurrently` as a root development dependency so the paired app processes run with one command and stop together when one side exits.
- Fixed the frontend dev script invocation so the Bun workspace command passes Vite host/port arguments correctly from the repo workflow.
- Updated the main repo workflow docs to reflect the new combined launcher and the corrected frontend startup command.

## 2026-04-12

- Added the first FastAPI-backed chat API scaffold for JurisAI, including session creation, message submission, SSE run streaming, artifact lookup, and selected-scheme updates.
- Reused the existing `BasicAgenticWorkflow` as the single orchestration path and exposed its streamed status events to the new HTTP layer instead of building a duplicate backend flow.
- Added workflow-stream events for answer deltas and artifact-ready notifications so the UI can react to retrieval artifacts and grounded reply generation in real time.
- Scaffolded a Bun + React + TypeScript + Vite frontend in `/Users/ratniel/JurisAI/web` with React Router, a dark-mode chat shell, and a right-rail top-schemes inspector.
- Added a UI-local `AGENTS.md` in `/Users/ratniel/JurisAI/web` documenting the same-repo frontend/backend layout, path handling, and Bun workflow expectations.
- Added repo-root Bun workspace scripts in `package.json` for frontend dev/build/lint and FastAPI local development convenience.

## 2026-03-31

- Added a generic `local_openai` generation provider so JurisAI can talk to any OpenAI-compatible local server rather than a single branded runtime.
- Added a local generation client that sends chat-style messages, strips leaked Qwen thinking blocks from plain-text replies, and falls back to JSON extraction for structured outputs.
- Added focused local-generation tests covering JSON parsing after `<think>` content and chat-message request shaping.
- Added repo docs that standardize the wording `OpenAI-compatible local server`, with runtime-specific tools documented as interchangeable deployment options.

## 2026-03-26

- Added a deterministic query-side retrieval intent model so retrieval now carries normalized query text, inferred topic intent, tag hints, and ignored-filter diagnostics.
- Normalized more user/classifier filters before retrieval, including location-style aliases such as `location -> state`, and validated explicit topic filters against the controlled topic taxonomy.
- Hardened retrieval ranking so state-aware searches now prefer matching-state schemes while still allowing central schemes as fallback when `level` is not explicitly pinned.
- Expanded Qdrant embedding documents so `topics` and key retrieval metadata are part of the embedded text rather than only stored as payload metadata.
- Improved retrieval hydration so raw Mongo lookups now prefer enriched companion collections and otherwise rebuild enriched fields before constructing chat-context schemes.
- Strengthened reply grounding so the responder is told not to present schemes as relevant when explicit user constraints are contradicted by the retrieved evidence.
- Added regression tests for retrieval intent normalization, state-or-central rule handling, topic-aware reranking, and raw-to-enriched hydration helpers.

## 2026-03-14

- Added a dual-profile Qdrant indexing path so each scheme produces:
  - `embedding_a` for `name + details`
  - `embedding_b` for `eligibility + benefits`
- Added Qdrant payload metadata needed for grounded retrieval, including Mongo references, embedding profile metadata, and retrieval-friendly scheme fields.
- Added retrieval utilities for deterministic filter mapping, dual-profile Qdrant search, and dedupe by Mongo-backed `scheme_id`.
- Replaced the workflow retrieval stub with a live retrieval execution step so the workflow now classifies, filters, queries Qdrant, dedupes hits, and passes grounded schemes into response generation.
- Validated the local test retrieval path on `test_schemes_vectors`, including a grounded retrieval case for an offline Maharashtra disability award scheme.

## 2026-03-25

- Updated enriched Mongo storage so `application_modes.online` and `application_modes.offline` are always present, using `null` when a value is unavailable.
- Rebuilt `jurisai.test_schemes_enriched` from `jurisai.test_schemes` so existing test documents now follow the stable `application_modes` shape.
- Updated the scraper persistence flow to upsert enriched production documents into `jurisai.schemes_enriched` alongside raw writes to `jurisai.schemes`.
- Updated architecture and workflow notes in project docs to reflect that `schemes_enriched` is now an active derived collection rather than a future target.

## 2026-03-24

- Split scheme contracts into two reusable model families:
  - `RawSchemeData` for scraped source documents
  - `EnrichedSchemeData` for transformed documents used by downstream retrieval and indexing
- Added a reusable topic catalog in [src/topic_catalog.py](/Users/ratniel/JurisAI/src/topic_catalog.py) for the agreed controlled topic set.
- Updated scraping to store FAQ content directly as plain-text `faq` instead of a `faqs` mapping.
- Switched the scraper and Beanie storage layer to write raw scheme documents only.
- Added a raw-to-enriched transformation pipeline in [src/data_ingestion/enrichment_pipeline.py](/Users/ratniel/JurisAI/src/data_ingestion/enrichment_pipeline.py).
- Updated the enrichment runner to transform raw test schemes into `test_schemes_enriched`.
- Removed `application_process` from the enriched document contract and replaced it with derived `application_modes`.
- Updated downstream indexing and agent models to read the enriched document shape.
- Added project tracking and maintenance docs: `TODO.md`, `completed_tasks.md`, and `agent.md`.
