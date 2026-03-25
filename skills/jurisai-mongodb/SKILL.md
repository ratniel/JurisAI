---
name: jurisai-mongodb
description: Use when working with JurisAI MongoDB collections, scheme enrichment, subset creation, verification, or collection-level data changes. Protect the raw scraped collection `schemes`; use `test_schemes` for testing and prefer new derived collections such as `test_schemes_enriched` for processed data.
---
# JurisAI MongoDB

Use this skill for MongoDB work in this repository.

## Safety rules

- Treat `jurisai.schemes` as the raw scraped source of truth.
- Do not modify `jurisai.schemes` unless the user explicitly asks for it.
- Use `jurisai.test_schemes` for experiments, validation, and sampling.
- Prefer writing transformed or enriched documents into a new collection such as `jurisai.test_schemes_enriched`.
- If a write is destructive, it must target only a test or derived collection.

## Default workflow

1. Inspect counts and sample documents first.
2. State the source collection and target collection before writes.
3. For preprocessing, copy into a derived collection instead of mutating raw data in place.
4. Verify with counts plus 3-5 sample documents after writes.

## Current collection conventions

- Raw scraped collection: `jurisai.schemes`
- Test subset: `jurisai.test_schemes`
- Enriched test subset: `jurisai.test_schemes_enriched`

## Useful commands

```bash
uv run python scripts/create_test_schemes.py
uv run python scripts/enrich_scheme_metadata.py --source-collection test_schemes --target-collection test_schemes_enriched --apply
uv run python - <<'PY'
from pymongo import MongoClient
client = MongoClient("mongodb://localhost:27017")
print(client["jurisai"].list_collection_names())
client.close()
PY
```
