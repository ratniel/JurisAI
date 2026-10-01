# Phoenix tracing

Tracing starts in the FastAPI lifespan or the CLI/eval launcher through `configure_phoenix_tracing`. Configure `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME`, and `PHOENIX_API_KEY` for Phoenix Cloud. Run `uv sync` and restart the backend after changing tracing dependencies or environment settings.

## Model calls

The shared setup enables LlamaIndex workflow, Google GenAI SDK, and LiteLLM instrumentation. Local OpenAI-compatible and OpenRouter clients resolve `litellm.completion` at call time, so importing the clients before server startup does not bypass instrumentation.

The official SDK instrumentors own LLM span lifetimes, prompts/responses, token usage, and error status. A small enrichment wrapper inside each instrumented call supplies:

| Attribute | Meaning |
| --- | --- |
| `llm.provider` | `google`, `openrouter`, or `local_openai` (the configured local OpenAI-compatible server; this does not infer its underlying vendor) |
| `llm.request.model_name` | Model sent in the request |
| `llm.response.model_name` | Effective model returned by the API, when available |
| `llm.model_name` | Effective model, falling back to the requested model |
| `llm.token_count.prompt`, `llm.token_count.completion`, `llm.token_count.total` | Usage reported by the provider |

A local server may echo a requested alias rather than its loaded model. Tracing cannot infer an effective model the server does not report. OpenRouter identifies the gateway; it does not imply that we know which upstream host OpenRouter selected.

The `llamaindex_google` adapter suppresses its framework LLM wrappers and re-enables instrumentation at the Google SDK boundary. This emits one LLM span per SDK call and avoids counting the same tokens twice. An explicit caller suppression remains respected.

Streaming Gemini spans finish when the stream is consumed, including error status for interrupted streams. Clarifications that return the classifier's question directly do not create a response-generation LLM span. Application retries create separate spans for each model call.

## Workflow and session context

`BasicAgenticWorkflow.run` initializes the session ID before spawning tasks and propagates it as standard `session.id`. Each step exposes LlamaIndex's active span as the current OpenTelemetry span. Provider calls and manual retrieval/hydration spans then belong to that workflow turn rather than separate traces. This shared path covers UI, CLI, and agentic-workflow evaluation callers.

The existing `jurisai.chat_session_id` and `jurisai.turn_id` step attributes remain available. Model names belong on LLM spans, since different workflow stages can use different models.

## Dashboard verification

Run a new turn after restarting. In Phoenix, open the turn, select an **LLM** child span, and inspect **Attributes** for `llm.model_name`, `llm.provider`, and token counts. Use the **Sessions** tab for a chat URL's session ID. In expression mode, filter spans with:

```python
session.id == "your-chat-session-id"
```

Inspect exported data independently of dashboard rendering:

```sh
px span list --project jurisai-agentic-poc --attribute session.id:your-chat-session-id --format json --no-progress
px trace get your-trace-id --project jurisai-agentic-poc --format json --no-progress
```

Historical traces cannot recover model/provider attributes that were never exported.

## Regression check

```sh
uv run python -m unittest discover -s tests/observability -v
```

The check uses real instrumentors and an in-memory exporter with fake provider responses. It checks local/OpenRouter identity and errors, Gemini sync/async and streaming behavior, the LlamaIndex Google adapter, requested/effective models, session propagation, and workflow parent links without external model calls.
