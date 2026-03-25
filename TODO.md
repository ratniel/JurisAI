# TODO

## Current Focus

- Promote the raw-to-enriched pipeline from `test_schemes -> test_schemes_enriched` to the full dataset flow `schemes -> schemes_enriched` after the test collection path is stable.
- Add evaluation before more architecture changes. Build a labeled set of 30-50 queries with expected schemes, expected filters, and expected exclusions so retrieval decisions can be measured instead of debated informally.
- Add a second-stage retrieval or rerank path. The current architecture already points in that direction in [docs/agentic_pipeline_progress.md](/Users/ratniel/JurisAI/docs/agentic_pipeline_progress.md).
- Expand structured metadata only where reliability is strong. Prioritize `state`, `level`, `provider_type`, `application_modes`, `scheme_type`, and selected numeric benefit fields before attempting brittle regex-only eligibility extraction.

## Data Pipeline

- Extract additional reliable fields from raw `application_process` text into enriched metadata where useful, especially official application URLs and contact numbers.
- Decide whether `documents_required` should stay as free text only or also gain a stable list representation in enriched documents.
- Revisit whether `faq` should later be chunked for retrieval instead of only stored as normalized plain text.

## Documentation And Maintenance

- Keep `TODO.md`, `completed_tasks.md`, and `agent.md` updated as decisions or scope change.
- Update relevant docs and skills whenever workflows, commands, contracts, or collection roles materially change.
