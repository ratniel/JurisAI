# JurisAI

JurisAI is a retrieval-grounded assistant for public-benefits and government-scheme discovery.

## Main Chat UI

The repo now includes the first main chat product surface in `/Users/ratniel/JurisAI/web`.

It uses:

- FastAPI for the Python chat/session API
- React + TypeScript + Vite for the UI
- Bun for frontend package management
- SSE for live workflow and answer updates

### Run both together

```bash
bun run dev
```

This root command starts both the FastAPI backend and the Vite frontend together for local development.

### Run the API

```bash
uv run python /Users/ratniel/JurisAI/scripts/run_chat_api.py --host 127.0.0.1 --port 8000
```

### Run the frontend

```bash
cd /Users/ratniel/JurisAI/web && bun run dev -- --host 127.0.0.1 --port 5173
```

Then open:

- [http://127.0.0.1:5173](http://127.0.0.1:5173)

The Vite dev server proxies `/api` calls to the local FastAPI server.

## Local inference wording

This repo uses the term `OpenAI-compatible local server` for self-hosted local generation.
That is the stable integration contract.

Examples of compatible runtimes include:

- LM Studio or `llmster` on Apple Silicon
- Ollama when using an Ollama-friendly model package
- vLLM on server-class GPU infrastructure
- SGLang on server-class GPU infrastructure

The application code should not depend on a specific runtime brand name.
It should depend only on an OpenAI-compatible chat endpoint plus a model name.

For the current local-model setup and environment variables, see [docs/openai_compatible_local_server.md](/Users/ratniel/JurisAI/docs/openai_compatible_local_server.md).
For the OpenRouter setup and project-specific defaults, see [docs/openrouter.md](/Users/ratniel/JurisAI/docs/openrouter.md).

## Agentic Debug UI

Launch the workflow debug UI with:

```bash
uv run python /Users/ratniel/JurisAI/scripts/run_agentic_debug_ui.py --host 127.0.0.1 --port 7861
```

The UI shows the full per-turn linear trace, including classifier output, the LLM-selected retrieval tool plan, each tool call input/output, the compact grounding pack, the top-schemes artifact, session memory, and the final grounded response.
