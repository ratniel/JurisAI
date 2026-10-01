# JurisAI

A government-scheme assistant with a FastAPI backend and React chat UI.

## Local development

Configure the repo `.env` for MongoDB, Qdrant, and the chosen LLM provider. Start local databases with `docker compose up -d`, install Python dependencies with `uv sync`, and frontend dependencies with `bun install`.

Run `bun run dev` from the repo root to start the API on port 8000 and Vite on port 5173. Open http://127.0.0.1:5173. The agentic provider defaults to `openrouter/free`; configure its API key or override the provider settings.

Validation: `bun run lint:web`, `bun run build:web`, and `uv run python -m unittest discover -s tests -p 'test_*.py'`.

The chat streams progress and answers, persists sessions in MongoDB, and shows a collapsible scheme shelf with full details and labeled source links. See `docs/production-data-pipeline.md` for indexing.
