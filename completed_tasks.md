# Completed Tasks

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
