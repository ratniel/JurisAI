# JurisAI

JurisAI is a government-scheme assistant with a FastAPI backend and React chat UI.

## Local development

Use the current `main` branch as the development baseline.
Create a goal-based branch before you change source files.
See [the Git workflow](docs/version_control_workflow.md).

1. Configure `.env` for MongoDB, Qdrant, and the selected LLM provider.
2. Start Docker Desktop.
3. Run `docker compose up -d` from the repository root.
4. Run `uv sync`.
5. Run `bun install --frozen-lockfile`.
6. Run `bun run dev`.
7. Open [the chat UI](http://127.0.0.1:5173/).

The launcher starts the API on port 8000 and Vite on port 5173.
A frontend startup failure stops both processes.
If Vite is missing, install the workspace dependencies again.
The provider default is `openrouter/free`.
Set its API key or configure another supported provider.

The Compose file binds MongoDB and Qdrant to the local host.
It keeps database contents in named volumes.
Do not remove these volumes during normal checkout cleanup.

## Checks

Run `bun run lint:web` for frontend lint.
Run `bun run build:web` for a production build.
Run `uv run python -m unittest discover -s tests -p 'test_*.py'` for backend tests.

The chat streams progress and answers.
It stores sessions in MongoDB.
It shows scheme details and labeled source links.
See [the data pipeline](docs/production-data-pipeline.md) for indexing.
