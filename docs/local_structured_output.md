# Local structured output

The local client sends a JSON Schema for structured calls.
The schema uses the response model name.
An explicit `response_format` overrides this default.

The client retains transport retries and structured-response retries.
If the server rejects `response_format`, the existing format fallback still applies.

For `qwen3.5-4b-mlx`, the client checks `reasoning_content` when `content` is empty.
This fallback applies only to structured calls.
The client validates the result against the response model.
Other models must return their result in `content`.
