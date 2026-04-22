# OpenRouter

This repo supports OpenRouter as a hosted OpenAI-compatible generation provider.

## Current project decisions

- Workflow provider key: `openrouter`
- Default base URL: `https://openrouter.ai/api/v1`
- Default model/router: `openrouter/free`
- API key env: `OPENROUTER_API_KEY`
- Keep `llamaindex_google` available because the main workflow still relies on LlamaIndex integration for Gemini.
- OpenRouter should reuse the shared OpenAI-compatible chat path, not a separate orchestration stack.

## Required environment variables

```dotenv
WORKFLOW_GENERATION_PROVIDER=openrouter
WORKFLOW_INTENT_PROVIDER=openrouter

OPENROUTER_API_KEY=
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TIMEOUT_SECONDS=60
OPENROUTER_ENABLE_THINKING=false
```

Optional attribution headers:

```dotenv
OPENROUTER_APP_NAME=JurisAI
OPENROUTER_HTTP_REFERER=
```

## Notes

- `openrouter/free` lets OpenRouter choose among free models and reports the selected upstream model in the response metadata.
- If `WORKFLOW_*_MODEL` is still set to a Gemini placeholder model and the provider is `openrouter`, JurisAI falls back to `OPENROUTER_MODEL`.
- OpenRouter requests should not send the local-only `chat_template_kwargs.enable_thinking` payload tweak used for some local runtimes.
