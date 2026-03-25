---
name: jurisai-qdrant
description: Use when working with JurisAI Qdrant collections, vector indexing, retrieval validation, payload metadata, or collection resets. Keep MongoDB as the source of truth and use separate Qdrant collections such as `test_schemes_vectors` for testing.
---
# JurisAI Qdrant

Use this skill for Qdrant work in this repository.

## Safety rules

- Treat MongoDB as the source of truth; Qdrant is a derived store.
- Use dedicated test collections for experiments, especially `test_schemes_vectors`.
- It is safe to recreate test Qdrant collections during indexing runs.
- Keep `mongo_ref` in every payload so results can be traced back to MongoDB documents.

## Default workflow

1. Confirm the Mongo source collection and Qdrant target collection.
2. Reindex test data into a dedicated test collection when changing payload shape.
3. Verify live hits after indexing, not just insert counts.
4. Check that payloads include filtering fields and `mongo_ref`.

## Current collection conventions

- Test vector collection: `test_schemes_vectors`
- Default profiles:
  - `embedding_a` = `name + details`
  - `embedding_b` = `eligibility + benefits`

## Useful commands

```bash
uv run python scripts/index_schemes_in_qdrant.py --source-collection test_schemes --collection test_schemes_vectors --recreate-collection
uv run python scripts/query_qdrant_schemes.py --collection test_schemes_vectors --query "offline Maharashtra disability award scheme"
```
