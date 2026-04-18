# Version Control Workflow

Last audited: 2026-04-19

## Purpose

This repo uses branch-per-goal development.
Each branch should represent one independent, reviewable outcome.

## Current PR Stack

- [#5](https://github.com/ratniel/JurisAI/pull/5) `feature/agentic-context-flow-release` -> `main`
  - agentic workflow foundation
- [#7](https://github.com/ratniel/JurisAI/pull/7) `feature/retrieval-eval-core` -> `feature/agentic-context-flow-release`
  - retrieval evaluation runner, dashboard, canonical eval assets, and corpus audit hardening
- [#6](https://github.com/ratniel/JurisAI/pull/6) `feature/chat-api-web-ui` -> `feature/retrieval-eval-core`
  - FastAPI chat API, SSE runtime, and the React web UI

## Branch Guidance

- Keep `#5` focused on the agentic foundation.
- Keep `#7` focused on retrieval/eval and retrieval-quality support code.
- Keep `#6` focused on the product-facing API and web UI.
- Retarget stacked PRs toward `main` only after their base PRs merge.

## Explicitly Excluded For Now

These areas are intentionally not in the active merge stack yet:

- BERTopic artifacts and runs
- topic-taxonomy experiment reports
- indexing and query validation utilities that still live as large script-owned workflows
- generated run artifacts under `evals/`

## Workflow Rules

- Start new independent work from `main`.
- Use goal-based branch names such as `feature/<goal>`, `fix/<goal>`, `enhancement/<goal>`, or `experiment/<goal>`.
- Push stable milestones early and open PRs with clear scope.
- Do not keep adding unrelated work to a branch that already has an open PR.
- Delete stale local and remote branches after merge or abandonment.
