# Stack Preferences

This repo now treats runtime configuration as a first-class part of the stack.

## Config source of truth

- Central settings live in [src/config/settings.py](/Users/ratniel/JurisAI/src/config/settings.py).
- The project uses `pydantic-settings` with `SettingsConfigDict(...)`.
- Preferred env naming uses nested keys with `__` via `env_nested_delimiter="__"`.
- Existing flat env names are still accepted for backwards compatibility where they are already common.

## Current stack preferences

- MongoDB is the source of truth for scheme documents.
- Qdrant is a derived retrieval index.
- Default Qdrant collection for development and validation is `test_schemes_vectors`.
- Retrieval uses two named vector profiles:
  - `embedding_a`: `name + details`
  - `embedding_b`: `eligibility + benefits`
- Default embedding backend is local sentence-transformers.
- Default embedding model is `all-MiniLM-L6-v2`.
- Default generation provider is Gemini.
- Phoenix tracing is optional but preferred during orchestrator runs.
- Retrieved schemes should be hydrated from Mongo and stored in `SessionSnapshot.relevant_schemes` for grounding and UI references.

## Preferred env keys

Preferred nested style:

```dotenv
APP__BASE_URL=https://www.myscheme.gov.in

MONGO__URI=mongodb://localhost:27017
MONGO__DATABASE_NAME=jurisai
MONGO__SCHEMES_COLLECTION=schemes
MONGO__TEST_SCHEMES_COLLECTION=test_schemes

QDRANT__URL=http://localhost:6333
QDRANT__DEFAULT_COLLECTION=test_schemes_vectors
QDRANT__PRODUCTION_COLLECTION=schemes_vectors

EMBEDDINGS__BACKEND=local
EMBEDDINGS__LOCAL_MODEL=all-MiniLM-L6-v2
EMBEDDINGS__GEMINI_MODEL=gemini-embedding-001

GEMINI__API_KEY=
GEMINI__MODEL=models/gemini-flash-latest
GEMINI__REASONING_MODEL=models/gemini-flash-latest
GEMINI__INTENT_MODEL=models/gemini-flash-lite-latest

WORKFLOW__GENERATION_PROVIDER=gemini
WORKFLOW__GENERATION_MODEL=models/gemini-flash-latest
WORKFLOW__INTENT_PROVIDER=gemini
WORKFLOW__INTENT_MODEL=models/gemini-flash-lite-latest
WORKFLOW__RETRIEVAL_LIMIT=5

PHOENIX__PROJECT_NAME=jurisai-agentic-poc
PHOENIX__COLLECTOR_ENDPOINT=
PHOENIX__API_KEY=
```

Legacy flat aliases still supported:

- `MONGODB_URI`
- `DATABASE_NAME`
- `SCHEMES_COLLECTION`
- `QDRANT_URL`
- `QDRANT_COLLECTION`
- `EMBEDDING_BACKEND`
- `LOCAL_EMBEDDING_MODEL`
- `GEMINI_EMBEDDING_MODEL`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `PHOENIX_API_KEY`
- `PHOENIX_COLLECTOR_ENDPOINT`
- `PHOENIX_PROJECT_NAME`

## Runbook

Index test schemes into Qdrant:

```bash
uv run python /Users/ratniel/JurisAI/scripts/index_schemes_in_qdrant.py --recreate-collection
```

Query Qdrant directly:

```bash
uv run python /Users/ratniel/JurisAI/scripts/query_qdrant_schemes.py --query "scholarship for minority students"
```

Run the full orchestrator workflow:

```bash
uv run python /Users/ratniel/JurisAI/scripts/run_agentic_poc.py \
  --message "I am a minority student in Maharashtra. What schemes can help me?"
```

Run the full orchestrator workflow with Phoenix tracing:

```bash
export PHOENIX_API_KEY="..."
export PHOENIX_COLLECTOR_ENDPOINT="..."

uv run python /Users/ratniel/JurisAI/scripts/run_agentic_poc.py \
  --trace-project "jurisai-agentic-poc" \
  --message "I am a minority student in Maharashtra. What schemes can help me?"
```

## Notes for future changes

- Add new runtime settings to `src/config/settings.py` first.
- Prefer nested models over new top-level flat settings.
- Keep default development behavior pointed at test collections unless we explicitly promote a production path.
- When adding new external services, document both:
  - preferred nested env keys
  - any flat aliases kept for compatibility
