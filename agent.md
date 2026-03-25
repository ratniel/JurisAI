# AGENT

## Maintenance Rules

- Update `TODO.md` whenever new open work, risks, or future follow-ups appear.
- Update `completed_tasks.md` whenever a meaningful implementation step lands.
- Update this file when the project operating rules or documentation expectations change.
- Update relevant documentation when contracts, collection names, retrieval flow, or indexing assumptions change.
- Update relevant skill notes under `/Users/ratniel/JurisAI/skills/` when stable workflows or commands should be preserved for future sessions.

## Current Contract Expectations

- Keep raw and enriched scheme models separate.
- Raw scheme documents are the scrape output and retain source fields such as `application_process`.
- Enriched scheme documents are transformation outputs and should not reintroduce removed raw-only fields unless there is an explicit decision to do so.
- FAQ content should be stored as normalized plain text in `faq`.
- `application_modes` is the enriched replacement for raw application-process detail storage.

## Current Collection Roles

- Raw production source: `schemes`
- Raw test subset: `test_schemes`
- Enriched test subset: `test_schemes_enriched`
- Future enriched production target still needs implementation: `schemes_enriched`

## Documentation To Check When Architecture Changes

- `TODO.md`
- `completed_tasks.md`
- `docs/agentic_pipeline_progress.md`
- `README.md` when user-facing setup or execution steps change
- Relevant files under `skills/` when those instructions become stale
