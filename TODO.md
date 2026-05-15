# TODO

## P0 Immediate Retrieval Workstream

### 1. Embedding profile v2

- Rebuild the dense-text strategy so the next Qdrant collection uses only:
  - `embedding_a = name + details`
  - `embedding_b = eligibility + benefits`
- Keep `tags`, `topics`, `level`, `provider`, `provider_type`, `state`, `ministry`, and similar fields in payload metadata and deterministic filters, not in the embedded text for v2.
- Update the indexer and any related docs/debug output so the embedded-field contract is explicit and visible.
- Re-index into a new Qdrant collection for comparison instead of mutating the current collection in place.

### 2. Retrieval-query generation experiment for the Vidarbha farmer record

- Focus first on the farmer query in `p1_vidarbha_farmer` before broadening the experiment surface.
- Resolve the golden must-retrieve schemes for that query from Mongo and export the exact source text used by both vector profiles into a file for offline comparison.
- Compare multiple retrieval-query formats and prompt variants against those golden profile texts.
- Compare multiple embedding models against the same golden profile texts.
- Choose the retrieval-query format and embedding model based on which combination produces the strongest similarity against the golden records, not by intuition alone.
- Keep the experiment artifacts and measurements reproducible under `evals/retrieval/runs/`.
- The stale topic-casing mismatch on the Nomic v2 subset has now been fixed by rebuilding the collection and keeping topic filters backward-compatible with legacy payload casing.
- The focused six-record filter-policy sweep is now complete. `state_only` is the best current policy on strict retrieval quality for this slice, and it is now the default operating mode. `topics_only` is not strong enough to gate retrieval on its own.
- Next, rerun the full 15-record eval on `eval_persona_schemes_vectors_v2_nomic_embed_text_v1_5` with query embeddings explicitly pinned to `nomic-ai/nomic-embed-text-v1.5`.
- Keep the shared `retrieval_filter_mode` controls in the harness and continue logging candidate filters separately from applied filters.
- Do not treat `state_hard_topics_soft` as the default end-to-end policy yet. The retrieval-core ranking looked promising, but the first agentic pass was confounded by Gemini rate-limit failures.

### 3. Topic normalization and metadata casing

- Audit topic casing end to end across:
  - classifier output
  - normalized retrieval filters
  - Qdrant payload metadata
  - any eval/debug displays
- Standardize topics to lowercase in future vector collections and keep the current query-time compatibility path for older title-cased payloads.
- Ensure the query-time normalization path also emits lowercase topics so filter matching is stable.
- Preserve visibility in debug output so we can see raw emitted topics and final applied topics separately.
- Expand targeted topic mappings only where the failure mode is concrete and measured. `engineering -> education + science & research` is now one such corrected case.

### 4. Retrieval harness and docs alignment

- Update the retrieval problem statement, retrieval status note, embedding strategy docs, and eval harness docs so they all reflect the v2 direction.
- Keep the shared retrieval evaluation runner and dashboard as the single harness path for these experiments.
- Add explicit documentation for:
  - the new collection naming/versioning
  - which fields belong in embeddings vs payload metadata
  - which query-generation prompt/version won the Vidarbha experiment

## P1 Next After P0

- Implement the beneficiary-aware retrieval and corrective-loop design captured in [docs/retrieval_profile_and_corrective_loop_design_2026_05_01.md](/Users/ratniel/JurisAI/docs/retrieval_profile_and_corrective_loop_design_2026_05_01.md), including:
  - separation of durable user-profile facts vs turn-specific facts
  - corrective retrieval before final answer generation
  - structured follow-up questions when one missing fact would materially improve retrieval
  - an agent-facing dynamic UI tool contract for deterministic button or option-based clarification
- Backfill existing production raw documents from `schemes` into `schemes_enriched` and verify parity now that new scraper writes mirror into the enriched production collection.
- Add a second-stage retrieval or rerank path only after the embedding/query-generation baseline is measurably better.
- Expand structured metadata only where reliability is strong. Prioritize `state`, `level`, `provider_type`, `application_modes`, `scheme_type`, and selected numeric benefit fields before attempting brittle regex-only eligibility extraction.
- Expand deterministic beneficiary and target-group extraction beyond query-side hints so fields like `minority`, `student`, `disabled`, caste/community markers, and education level can become stronger than tag/topic-only signals.
- Add a beneficiary-aware precision pass for the next retrieval experiment, especially for same-state wrong-beneficiary distractors like `Mahila Kisan Yojana (Maharashtra)` surviving farmer queries.
- Refactor `RelevantScheme` into a lean chat-context model instead of a near-duplicate of enriched scheme data.

## Data Pipeline

- Extract additional reliable fields from raw `application_process` text into enriched metadata where useful, especially official application URLs and contact numbers.
- Decide whether `documents_required` should stay as free text only or also gain a stable list representation in enriched documents.
- Revisit whether `faq` should later be chunked for retrieval instead of only stored as normalized plain text.
- Plan late chunking for `benefits`, `eligibility`, and `faq` on top retrieved schemes only, so detailed follow-up answers can be generated without paying the cost of full-dataset LLM structuring.
- Add a UI follow-up path near chat for the top 3 retrieved schemes. Clicking one of the popup actions should trigger a brief scheme-details response backed by the late-chunked fields for that selected scheme.
- Extend the new FastAPI chat API with:
  - durable run replay after reconnect
  - explicit selected-scheme follow-up handling in the UI
  - session list/history views
  - richer artifact summaries instead of long raw detail blocks
- Add a stronger frontend operator mode that can link out to workflow trace payloads and Phoenix trace ids without mixing that into the default user chat surface.
- Expand topic mapping coverage for currently unmapped or weakly mapped tags before topics are treated as a stronger retrieval signal across the full dataset.

## Documentation And Maintenance

- Keep `TODO.md`, `completed_tasks.md`, and `AGENTS.md` updated as decisions or scope change.
- Update relevant docs and skills whenever workflows, commands, contracts, or collection roles materially change.
- Keep the repo-root `bun run dev` workflow documented as the default way to launch the main UI and FastAPI backend together for local product development.
