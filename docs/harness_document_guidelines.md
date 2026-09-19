# Harness Document Guidelines

Use these repo conventions when writing or updating `AGENTS.md`, skills, and other versioned harness docs.

## Purpose

- Keep harness documents aligned with the real project structure and current implementation.
- Prefer small, accurate updates over broad notes that drift away from the codebase.
- Update harness documents in the same workstream as the code or product decision they describe.

## Project-structure alignment

- Repo-root `AGENTS.md`:
  - Holds repo-wide rules, architecture, stack choices, workflow expectations, and cross-stack decisions.
  - Use it for guidance that applies across `./src`, `./web`, scripts, evals, and docs.
- Surface-specific `AGENTS.md` files such as `./web/AGENTS.md`:
  - Hold local instructions for one app surface or workspace only.
  - Do not duplicate repo-wide guidance unless the local surface needs a narrowed version of it.
- Skills under `./skills/*/SKILL.md`:
  - Capture reusable workflows for a specific subsystem, tool, datastore, or operational task.
  - Keep them procedural and concrete: when to use the skill, safety rules, current conventions, and canonical commands.
- Private working notes such as repo-root `TODO.md`, `completed_tasks.md`, and ad hoc retrieval status snapshots:
  - Are local-only notes, not canonical harness docs.
  - Keep them in a gitignored path such as `.local/notes/` or `.local/experiments/`.
  - Do not add them to git unless the user explicitly asks for a versioned tracker.

## Writing rules

- Write according to ownership boundaries in the repo:
  - backend and eval guidance should point to `./src`
  - frontend guidance should point to `./web`
  - shared workflow guidance should stay at repo root or under `./docs`
- Prefer current decisions, active conventions, and stable commands over historical narrative.
- Keep instructions explicit where ambiguity would cause drift:
  - source-of-truth files
  - collection names
  - command entrypoints
  - API or retrieval contracts
  - artifact locations
- When a workflow has a canonical structured ledger such as a CSV run log, prefer that ledger over hand-maintained status tables and keep the generation path documented.
- Avoid parallel old/new instructions. When a workflow changes, replace the outdated path unless the old one is still intentionally supported.
- Do not commit private scratch markdown just because it was useful during implementation. If a note is only for local bookkeeping, keep it out of the repo.

## Update expectations

- Update these harness documents whenever we make an important project decision and whenever that decision is implemented in the codebase.
- Treat documentation updates as part of the implementation, not as optional follow-up cleanup.
- When architecture, workflow, commands, contracts, retrieval policy, storage conventions, or evaluation paths change, update the relevant harness files in the same change set.
- When a reusable workflow changes, update the relevant skill so future agent runs follow the new behavior.
- When a decision becomes repo-wide, move or summarize it in the repo-root `AGENTS.md`; when it is local to one surface, keep it in that surface's local `AGENTS.md`.
- When a decision is worth preserving publicly, distill it into a stable doc under `docs/` instead of committing private trackers or scratch notes.

## Minimum maintenance checklist

- `AGENTS.md`: update for new rules, architecture decisions, workflow expectations, or repo structure changes.
- `skills/*/SKILL.md`: update for new commands, safety rules, datastore conventions, or subsystem workflows.
- Relevant docs in `./docs`: update when harness instructions reference behavior that changed in code.
- Versioned structured ledgers such as `evals/retrieval/runs/run_log.csv`: keep them programmatically regenerable from canonical artifacts whenever possible.
- Local-only note files: keep them gitignored and out of version control unless the user explicitly asks to publish them.
