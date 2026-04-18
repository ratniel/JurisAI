# Frontend Streaming And Backend Integration Note

## Purpose

Capture the first frontend-facing plan for a user chat product built on top of the current backend workflow.

This note is intentionally brief and pragmatic. It is not a full frontend spec yet.

## Product Direction

The current thinking is shifting in a good direction:

- from "how does the workflow run"
- toward "what does the user see, when do they see it, and which backend contracts make that possible"

That is the right lens for the next milestone.

## Existing Backend Strengths

The current backend already has pieces we can build on:

- structured workflow stages in [src/agentic/workflow.py](/Users/ratniel/JurisAI/src/agentic/workflow.py)
- streamed `WorkflowStatusEvent` objects in [src/agentic/models.py](/Users/ratniel/JurisAI/src/agentic/models.py:259)
- grounded retrieval before answer generation
- Phoenix trace correlation for operator visibility
- hydrated scheme records already suitable for UI references

The backend does not yet expose a stable user-chat API contract. That is the main next layer.

## Existing Docs That Help

These existing notes are useful inputs:

- [docs/retrieval_eval_plan.md](/Users/ratniel/JurisAI/docs/retrieval_eval_plan.md)
  - already proposes a top-3 scheme follow-up UI near chat
- [docs/retrieval_status_2026_04_week1.md](/Users/ratniel/JurisAI/docs/retrieval_status_2026_04_week1.md)
  - already defines a UI/debug requirement for inspectable agentic retrieval runs
- [docs/retrieval_eval_dashboard.md](/Users/ratniel/JurisAI/docs/retrieval_eval_dashboard.md)
  - already shows the kinds of payloads and live record views that are useful in operator mode

## Recommended Frontend Stack Direction

- React
- TypeScript
- Bun for local dev and package/runtime convenience
- Vite for the frontend dev server and production build
- FastAPI for the Python HTTP layer that exposes chat/session/run endpoints
- SSE first for streamed stage events and answer tokens
- WebSocket only if bidirectional control becomes necessary later

## Same-Repo Layout

Keep the first implementation in one repo:

- frontend app in `/Users/ratniel/JurisAI/web`
- FastAPI backend in `/Users/ratniel/JurisAI/src/api`
- shared docs and contracts at the repo root under `/Users/ratniel/JurisAI/docs`

Local development should run as two servers:

- Vite frontend on `127.0.0.1:5173`
- FastAPI backend on `127.0.0.1:8000`

The canonical repo-root launcher for this two-server development mode is:

- `bun run dev`

The Vite dev server should proxy `/api` calls to FastAPI so the browser uses one local origin pattern during development.

## Streaming Recommendation

For the user endpoint, stream:

- lifecycle events
- answer tokens
- artifact-ready notifications

Do not stream hidden chain-of-thought to end users.

Recommended event types:

- `run_started`
- `stage_update`
- `answer_delta`
- `artifact_ready`
- `run_completed`
- `run_failed`

## Encryption Note: Future scope

"Encrypted streaming" should be interpreted in layers:

1. TLS for transport
2. authenticated session-bound stream access
3. encrypted artifact storage at rest if needed

If stronger message-level encryption is desired later, it should be added after the product API is stable.

For the first release, this functionality will. be skipped and implemented before productionaizing.
TLS plus authenticated access is the right baseline for encrypted transactions.

## Proposed User-Facing API Surface

### Session lifecycle

- `POST /chat/sessions`
  - create a new chat session
- `GET /chat/sessions/:session_id`
  - fetch session metadata and memory summary

### Message send and run execution

- `POST /chat/sessions/:session_id/messages`
  - submit a user message and create a run
- `GET /chat/sessions/:session_id/runs/:run_id/stream`
  - SSE stream for status updates, answer deltas, and artifact readiness

### Artifact access

- `GET /chat/sessions/:session_id/artifacts`
  - list artifacts for the session
- `GET /chat/sessions/:session_id/artifacts/:artifact_id`
  - fetch full artifact payload

### Follow-up scheme selection

- `POST /chat/sessions/:session_id/selected-scheme`
  - set or clear the scheme the user is focusing on

## Recommended Response Pattern

### On each user message

1. open or resume session
2. create run
3. stream stage events
4. stream answer tokens
5. attach top-schemes artifact when ready
6. persist updated session memory

### Artifact behavior

- top-schemes artifact is generated after retrieval
- it may be concurrent with answer generation
- if rate-limited, it is deferred and attached later

## UI Surfaces

### User chat surface

- chat transcript
- streaming answer
- small stage indicator
- top-schemes side panel or inline card strip
- selectable scheme details drawer

### Operator/debug surface

- full workflow trace
- tool inputs and outputs
- raw retrieval metadata
- Phoenix trace links

These should remain separate modes even if they live in the same app.

## Backend Changes Needed

- expose workflow streaming through an HTTP layer
- add session storage keyed by `chat_session_id`
- add artifact persistence and retrieval
- separate prompt-facing context builders from UI/debug payload builders

## Suggested First Release Scope

- one user chat endpoint
- SSE streaming
- session memory persistence
- top-schemes artifact retrieval
- selected-scheme follow-up support

Do not block the first release on:

- true end-to-end encrypted payloads
- multi-device sync
- full frontend debug console
- WebSocket-only transport

## Related Files

- [src/agentic/workflow.py](/Users/ratniel/JurisAI/src/agentic/workflow.py)
- [src/agentic/models.py](/Users/ratniel/JurisAI/src/agentic/models.py)
- [docs/retrieval_eval_plan.md](/Users/ratniel/JurisAI/docs/retrieval_eval_plan.md)
- [docs/retrieval_status_2026_04_week1.md](/Users/ratniel/JurisAI/docs/retrieval_status_2026_04_week1.md)
- [docs/retrieval_eval_dashboard.md](/Users/ratniel/JurisAI/docs/retrieval_eval_dashboard.md)
