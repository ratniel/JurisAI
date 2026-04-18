# OpenAI-Compatible Local Server

This repo uses the phrase `OpenAI-compatible local server` as the stable contract for local self-hosted generation.

That contract means:

- JurisAI sends chat-style `messages` to an OpenAI-compatible endpoint.
- The runtime behind that endpoint is replaceable.
- The app should not be coupled to LM Studio, Ollama, vLLM, or SGLang by name.

## Current local model

- Default local model: `mlx-community/Qwen3.5-4B-MLX-4bit`
- Current provider key: `local_openai`

## Required environment variables

```dotenv
WORKFLOW_GENERATION_PROVIDER=local_openai
WORKFLOW_INTENT_PROVIDER=local_openai

LOCAL_GENERATION_BASE_URL=http://127.0.0.1:1234/v1
LOCAL_GENERATION_API_KEY=not-needed
LOCAL_GENERATION_MODEL=mlx-community/Qwen3.5-4B-MLX-4bit
LOCAL_GENERATION_TIMEOUT_SECONDS=60
LOCAL_GENERATION_ENABLE_THINKING=false
```

If you want to keep the classifier on Gemini and only move final response generation local, set only:

```dotenv
WORKFLOW_GENERATION_PROVIDER=local_openai
LOCAL_GENERATION_BASE_URL=http://127.0.0.1:1234/v1
LOCAL_GENERATION_MODEL=mlx-community/Qwen3.5-4B-MLX-4bit
LOCAL_GENERATION_ENABLE_THINKING=false
```

## Compatible runtime examples

### Apple Silicon local development

- LM Studio
- `llmster`

These are convenient options for MLX-backed local serving on macOS.

### Consumer local install

- Ollama

Use this when you want a simpler end-user install flow, but note that model packaging may differ from the MLX artifact used in development.

### Server deployment

- vLLM
- SGLang

Use these when you move to Linux GPU infrastructure and care more about throughput and server operations than local macOS ergonomics.

## Tool calling and chat templates

The local client uses chat-style `messages` so the serving runtime can apply the model's tokenizer chat template.

For Qwen-family models:

- tool-calling behavior depends on the server correctly applying the tokenizer template
- plain-text replies should usually run with thinking disabled
- structured outputs should tolerate `<think>...</think>` content when a backend ignores the thinking toggle

## Design rule

When updating docs, code comments, or setup instructions:

- prefer `OpenAI-compatible local server`
- avoid naming a specific runtime unless the distinction is operationally important
