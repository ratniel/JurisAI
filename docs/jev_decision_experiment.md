# Jev decision comparison

This experiment compares two bounded decisions with the existing
`UserIntentClassifier`: `primary_intent` and `needs_clarification`. It does not
change the production classifier, run retrieval, or generate answers. Jev uses
two Choice questions in one request to the [TypeSafe HTTP API](https://docs.typesafe.ai/api).
No new package is required.

## Run

Run commands from the repository root after installing the existing dependencies
with `uv sync`. Use the shared golden corpus at
`eval/retrieval/golden_classifier_retrieval_v1.jsonl`. In a separate worktree,
point `EVAL__ARTIFACTS_ROOT` at the existing canonical seed directory rather than
maintaining a second corpus.

Inspect requests without credentials or model calls:

```sh
uv run python scripts/compare_jev_decisions.py --dry-run
```

For a live comparison, set `TYPESAFE_API_KEY` in the environment or the gitignored
repo-root `.env`. Start the local OpenAI-compatible server, then run:

```sh
uv run python scripts/compare_jev_decisions.py \
  --intent-provider local_openai \
  --intent-model 'mlx-community/Qwen3.5-4B-MLX-4bit' \
  --record-ids retrieval_eval_001
```

Use the actual loaded local model name. Omit `--record-ids` to compare all shared
cases. Omitting provider/model overrides uses existing workflow settings.
`--jev-model` defaults to `jev-latest`; the returned model version is retained
per record. `--confidence-threshold` defaults to 0.8 as a diagnostic threshold,
not a validated production routing policy.

The models receive the same user-message/session-context text, with empty session
memory for these single-turn retrieval cases. Jev never sees baseline predictions,
gold labels, expected filters, or positive/distractor scheme IDs. Both question
definitions and the baseline system prompt are saved for inspection.

## Interpret results

The existing corpus has retrieval labels, not intent or clarification labels.
Agreement measures whether the two systems match; it does not establish which
one is correct. Missing gold labels produce `null` accuracy, not invented scores.
Optional human-reviewed labels can be added to the same golden records:

```json
{"expected_primary_intent": "scheme_discovery", "expected_needs_clarification": false}
```

These fields supplement a complete existing golden record. They are not a new
dataset format. Label before inspecting predictions. The existing corpus is
discovery-heavy and cannot establish performance on small talk, out-of-scope
requests, follow-ups, or clarification-required turns.

For each decision, the report separates agreement, labeled/scored counts,
accuracy over successful labeled responses, and confident errors. Failed calls
are reported separately and excluded from accuracy/agreement denominators.
The baseline's single confidence value is used only for intent; it supplies no
separate clarification confidence. Confidence values from the two systems are
not assumed to have equivalent calibration.

Successful-call median latency, full classifier outputs, Jev probability
distributions, resolved Jev model version, and available baseline invocation/token
metadata are retained. Jev gets one attempt with a 30-second timeout; the existing
classifier keeps its provider retry policy. Errors contain exception type and HTTP
status, without provider error bodies. A run with call failures exits with code 2.

This measures the decision stage only. Baseline latency includes query generation
and fact extraction, which Jev does not replace. Token usage is not a dollar-cost
estimate; baseline usage may be unavailable with some providers. No end-to-end
speed or cost improvement should be claimed from this comparison alone.

## Artifacts and checks

Implementation lives in `src/eval/jev_decision_eval.py`; the CLI is a thin wrapper.
Runs use `evals/agentic_workflow/runs/agentic_workflow_eval_jev_decisions_<timestamp>.json`,
plus the existing `latest.json` and regenerable `run_log.csv`. Dry runs have
`eval_mode=jev_decisions_dry_run`; live runs have `eval_mode=jev_decisions`.
The ledger indexes runs; detailed decision metrics stay in JSON. These files are
gitignored. Existing full-workflow artifact writing regenerates the same ledger
and includes these runs by their shared filename prefix.

```sh
uv run python -m unittest tests.eval.test_jev_decision_eval -v
```

Keep the experiment offline until it shows useful accuracy on representative
human-labeled cases. Do not add reranking, eligibility judgments, or a replacement
orchestrator to this experiment.
