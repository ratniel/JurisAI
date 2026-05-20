# JurisAI Agent Notes

## Project Intention

- Build an agentic legal-schemes assistant that can classify user intent, retrieve the right schemes, and later generate grounded answers.
- Keep retrieval explainable and debuggable. Every retrieval run should show classifier output, normalized queries, filters, raw hits, and final results.
- Optimize for correctness before sophistication. The current priority is to make retrieval fetch the right schemes with the right metadata filters. Reranking is intentionally disabled for now.

## Active Retrieval Decisions

- The eval path must use the agentic classifier. Do not add new eval modes that bypass classifier output unless there is a clearly separated debugging need and explicit approval.
- The rule engine must translate detected state into schema-native vector filters:
  - `level = "state"`
  - `provider = "<state_name>"`
- Central fallback is still allowed for relevant central schemes, but the state-derived filter path must be visible in debug output.
- Retrieval strategy should move toward tool-based delegation rather than one hard-coded pipeline.
- For now, the intended retrieval tools are:
  - semantic search
  - state-scoped search
  - topic-scoped search
- The LLM/orchestrator should decide which retrieval tool to use, whether to pass filters, and how to compose retrieval with final answer generation.
- Keep the base retrieval primitives simple and explicit. Do not hide too much policy inside a single monolithic search function.
- Use one shared eval corpus. Do not introduce persona-scoped vector collections or persona-only retrieval shortcuts.
- Use one shared retrieval evaluation runner in `src/eval/retrieval_eval.py`.
- The dashboard and CLI must consume the same shared evaluation logic.
- Retrieval-eval run artifacts belong only under `evals/retrieval/runs/`.
- The canonical retrieval experiment ledger is `evals/retrieval/runs/run_log.csv`.
- Keep `run_log.csv` aligned with the JSON run artifacts; do not maintain separate ad hoc experiment tables when the CSV can be regenerated from the persisted runs.
- `eval/retrieval/` is for canonical seed assets only:
  - `personas_v1.yaml`
  - `shortlists_v1.yaml`
  - `golden_classifier_retrieval_v1.jsonl`
- Until a broader clean eval says otherwise, keep `state_only` as the default retrieval filter mode and treat `state_hard_topics_soft` as an experimental ranking candidate rather than the active default.

## Current p1 Direction

- `p1_vidarbha_farmer` should be evaluated against real corpus conditions, not an imagined Maharashtra-only corpus.
- Central agriculture schemes are valid positives for p1.
- Same-state wrong-beneficiary schemes like `Mahila Kisan Yojana (Maharashtra)` are explicit distractors unless the query states those beneficiary constraints.
- If p1 keeps failing after correct state filtering is applied, treat it as a retrieval-quality issue, not a state-filter plumbing issue.

## Stack

- Python 3.11
- `uv` for dependency and environment management
- FastAPI for the main chat/session HTTP API
- Gradio for the retrieval eval dashboard
- React + TypeScript + Vite for the main user-facing UI
- Bun for frontend package management and local UI commands
- MongoDB as the source of truth for scheme documents and eval subset builds
- Qdrant for vector retrieval
- LM Studio as the preferred local OpenAI-compatible LLM server during local agentic testing
- Phoenix for tracing

## UI And Repo Layout

- The main UI lives inside this same repo at `/Users/ratniel/JurisAI/web`.
- Treat this as one repo with two app surfaces:
  - Python backend under `/Users/ratniel/JurisAI/src`
  - Bun/Vite frontend under `/Users/ratniel/JurisAI/web`
- Do not split the frontend into a separate repo unless explicitly requested.
- Prefer keeping the FastAPI contract and React UI aligned through shared repo docs rather than duplicating API expectations in frontend-only notes.
- Dark mode is the required default for the main UI.

## Working Commands

- Prefer `uv run ...` for scripts and tests when possible.
- If the repo-local virtualenv is already in use, `.venv/bin/python ...` is acceptable.
- Start local infra through the repo `docker-compose.yml` when MongoDB or Qdrant is missing.
- For local chat-product development, prefer the repo-root combined launcher:
  - `bun run dev`
- Frontend commands should use Bun from the repo root or the `web/` workspace:
  - `cd /Users/ratniel/JurisAI/web && bun run dev -- --host 127.0.0.1 --port 5173`
  - `bun --cwd /Users/ratniel/JurisAI/web run build`
- The FastAPI chat server runs via:
  - `uv run python /Users/ratniel/JurisAI/scripts/run_chat_api.py --host 127.0.0.1 --port 8000`

## Code Hygiene Rules

- Remove redundant paths instead of leaving old and new implementations side by side.
- Keep evaluation logic in `src/eval/` and keep scripts as thin wrappers.
- Do not reintroduce reranking code until retrieval correctness is strong enough to justify it.
- Prefer adding new retrieval modes as explicit tools/interfaces rather than baking more branching logic into the default retriever.
- Keep generated run artifacts out of git.
- When a doc describes the current implementation, update it in the same workstream as the code change.

## Git Workflow

- Every branch must be goal-based and feature-wise: one branch, one independent outcome.
- Allowed branch types are:
  - `feature/<goal>` for a user-facing feature or a discrete product slice
  - `fix/<goal>` for a bug fix
  - `enhancement/<goal>` for a scoped improvement that is not a brand-new feature
  - `experiment/<goal>` for retrieval investigations and short-lived search experiments
- Before starting a new task, check the current branch. If the task is not the same goal, create a new branch from `main` instead of reusing the old one.
- Do not mix unrelated backend, frontend, eval, infra, and docs work on the same branch unless that combination is the single reviewed goal of the branch.
- Keep commits scoped to one clear outcome whenever possible.
- If a task reaches a stable milestone, push the branch and open or update a PR with `gh` instead of stacking more unrelated work on top of it.
- After opening a PR, explicitly ask the user to review it.
- Do not keep building new work on a branch that already has an open PR unless the new changes are still part of that PR's exact goal.
- When a branch is merged or abandoned, clean it up locally and remotely.

## Maintenance Expectations

- Use `docs/harness_document_guidelines.md` as the shared convention for writing and updating repo-root and surface-local harness documents.
- Update this file when project rules or architectural decisions change.
- Update `README.md` when setup or execution steps change.
- Update `docs/version_control_workflow.md` when the branching or PR process changes, or when we complete a new branch/PR audit.
- Update retrieval docs when eval flow, collection names, or indexing assumptions change.
- Update retrieval experiment logging docs when the run ledger path, logged fields, or regeneration workflow changes.
- Update frontend/backend integration docs when the FastAPI contract, Bun workspace layout, or streaming UI behavior changes.
- Do not version private working notes such as repo-root `TODO.md`, `completed_tasks.md`, or ad hoc retrieval status snapshots. Keep those in a local-only gitignored path such as `.local/notes/` or `.local/experiments/`.
- Version only reviewer-facing docs that describe stable behavior, shipped workflow changes, or user-visible decisions.
- If a retrieval investigation needs a versioned doc, write a distilled public note under `docs/` instead of committing scratch notes or personal trackers.
