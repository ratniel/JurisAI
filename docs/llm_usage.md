# LLM usage records

Each workflow result includes `llm_usage_records`.
The records identify classification, planning, and answer generation.
Session memory keeps cumulative `llm_usage_totals`.
Old sessions start with zero totals.

The local client keeps its existing dictionary-based `invocation_history`.
Its `last_invocation_metadata` now follows the typed client contract.
That record uses the response model when the provider supplies one.
The workflow totals use the latest response for each stage.
They are not a billing total for all retry attempts.

The Google adapter records provider and model identity.
It reports zero usage when no token count is available.
Gemini token aliases use the first valid integer value.

These records do not replace Phoenix LLM span instrumentation in PR #19.
The API stores them through the existing workflow result and session models.
