# JurisAI

An agentic assistant for finding government schemes.

## Jev experiment

The offline [Jev decision comparison](docs/jev_decision_experiment.md) compares
intent and clarification decisions with the existing classifier on the shared
eval corpus. It does not change production routing.

```sh
uv sync
uv run python scripts/compare_jev_decisions.py --dry-run
```

The shared seed assets must be present under `eval/retrieval/`, or selected through
`EVAL__ARTIFACTS_ROOT`. Live comparisons also require `TYPESAFE_API_KEY` and a
configured baseline model; see the experiment guide for commands and limitations.
