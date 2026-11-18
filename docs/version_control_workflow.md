# Git workflow

## Development baseline

Use `main` as the integration branch.
Create one branch for each independent goal.
Use `feature/`, `fix/`, `enhancement/`, or `experiment/` as the branch prefix.
Base new work on current `main` unless a dependency requires an explicit stack.

Before changing a checkout, inspect its branch and working files.
Do not put unrelated changes on an open PR branch.
Keep commits limited to one reviewable outcome.
Push a stable branch and open a PR.
Ask for review after opening the PR.

## Preserve work before cleanup

Check tracked changes, untracked files, ignored files, and unpushed commits.
Save important files before removing a checkout.
Verify the saved contents.
Preserve credentials only in private local storage.
Keep run outputs and private notes out of commits.
Do not delete database volumes as part of checkout cleanup.

Use the app archive action for a managed worktree.
Keep an experiment branch while its result is under review.
Remove a branch only after its work is merged or explicitly abandoned.
An old checkout is not proof that its work can be discarded.

## Audit on 2026-11-18

PR #18 is the shipped UI and API baseline on `main`.
The old context-flow checkout contained several unrelated changes.
Its important source files were preserved before the primary checkout moved to `main`.
Selected source changes were extracted into independent draft PRs.
The extraction retained the current retry, grounding, and hydration behavior.

| Branch | Review |
| --- | --- |
| `enhancement/nomic-retrieval-defaults` | #20: model and matching collection defaults |
| `fix/lmstudio-structured-output` | #21: local structured-output requests |
| `experiment/hybrid-retrieval-eval` | #22: explicit experimental search controls |
| `enhancement/llm-usage-accounting` | #23: usage records and session totals |
| `fix/retrieval-ledger-export` | #24: shared ledger export entrypoint |

PRs #6 and #8 contain older UI work.
Compare useful regression coverage before closing them.
PR #17 includes the clarification direction from #15.
Review their overlap before merging either branch.
PR #19 contains Phoenix instrumentation.
A checkout removal does not close its PR or remove its branch.

The existing main baseline has type-check failures outside these extracted changes.
Record focused checks and any skipped hook in each PR description.
Do not claim a full type-check pass from unit tests alone.
