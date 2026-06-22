# Implementation Plan: Dialogue Message Vertical Slice

Issue: https://github.com/patex1987/python-agent-with-idp/issues/1

Branch: `issue-1-dialogue-message-vertical-slice`

Last reviewed: 2026-06-19

## 1. Summary

Build the first demoable agent shell around `Dialogue` and `Message`, with no real LLM calls. The slice should prove the product-facing chat API and the internal control-plane/data-plane split:

- Control plane: public API, `Dialogue`, `Message`, ownership, intake, dispatch, cancellation intent.
- Data plane: worker loop, claim/lease, deterministic fake execution, internal events, terminal completion.

The public frontend API must be `Dialogue` / `Message` based. `AgentExecution` remains an internal runtime concept and shared CP/DP contract, not an end-user resource.

The first implementation stays in-memory for fast iteration, but the design must use the same ports and boundaries expected from future DB+broker, DB+SQS, or Temporal-based implementations.

## 2. Goals

- Provide a demoable chat shell with deterministic fake assistant responses.
- Prove that public chat state is decoupled from worker execution state.
- Replace public `AgentExecution` HTTP routes with product-level `Dialogue` and `Message` routes.
- Keep `AgentExecution` as the internal execution attempt that produces one assistant message.
- Introduce directional CP -> DP and DP -> CP boundaries:
  - CP -> DP dispatcher methods.
  - DP -> CP versioned internal events.
- Add a minimal real event contract now, including event types, schema versions, payload models, and event metadata.
- Keep `contracts/` pure and dependency-light as the shared CP/DP boundary.
- Implement in-memory stores and dispatching through protocols so later Piccolo/Postgres, Rabbit/SQS, or Temporal adapters are replacement adapters, not redesigns.
- Add enough OpenAPI docs, curl examples, and tests to support a simple UI after this PR.
- Do a full cleanup of stale `Conversation` / `Turn` / `Run` documentation and public route leftovers that conflict with the current vocabulary.

## 3. Non-goals

- No real LLM or model-client port in this issue.
- No tool calling, tool registry, tool approval, shell execution, filesystem edits, MCP, or sandboxing.
- No idempotency implementation yet.
- No audit log implementation yet.
- No durable database schema or Piccolo migrations.
- No public SSE/websocket/message-event stream.
- No public exposure of internal `AgentExecution` events.
- No regenerate/recreate endpoint yet.
- No delete/archive lifecycle for dialogues or messages.
- No frontend UI implementation.
- No automated import-boundary checks yet.
- No full event sourcing, snapshots, upcasters, replay UI, or event-store OCC.
- No commits, push, or PR opening by the agent unless explicitly requested by the user.

## 4. Current State

The repository is a Python 3.12 FastAPI service scaffold using `svcs`, Piccolo/PostgreSQL infrastructure, structured logging, authentication middleware, and in-memory agent execution experiments.

Relevant current evidence:

- `docs/plans/TODO.md` says the intended vertical slice is: user message -> dialogue/message state -> async `AgentExecution` -> execution events -> assistant message finalization.
- `llm_agent/docs/DOMAIN_VOCABULARY.md` already defines the target hierarchy: `Dialogue` contains `Message`s; an assistant `Message` is produced by an `AgentExecution`.
- `llm_agent/llm_agent/api/http/v1/routes/agent.py` currently exposes public operational `AgentExecution` endpoints. These should be removed from the public API in this issue.
- `llm_agent/llm_agent/services/agent/orchestrator.py` currently creates an execution request but hardcodes `user_id` and discards request history.
- `llm_agent/local_runtime/agent_execution_store/intake.py` and `processing.py` hold current in-memory execution state and append execution events.
- `llm_agent/local_runtime/event_log/in_memory.py` stores append-only per-execution events with `sequence_nr` and timestamps.
- `llm_agent/agent_execution_worker/in_memory/consumer.py` claims executions, sends heartbeats, runs the executor, and sets terminal execution state.
- `llm_agent/llm_agent/api/http/middlewares/authentication.py` stores authenticated `user_id` in request scope state.
- `testing_payloads/http_api_curl.sh` exists and should be updated with the new product API flow.

Local agent inspiration index:

- `/home/patex1987/development/gh_agent_projects/_index/patterns/runtime-state.md` maps session/thread -> `Dialogue`, message/turn -> `Message`, and run/task/job -> `AgentExecution`.
- The local index groups execution lifecycle, event logs, event streaming, checkpointing, cancellation, idempotency, and resumability as runtime-state concerns.
- `/home/patex1987/development/gh_agent_projects/_index/patterns/tools-policy-security.md` keeps tools, approvals, permissions, shell/filesystem execution, secrets, and sandboxing as a separate cluster. This supports deferring tools until the execution envelope is safer.

Local Programming KB notes:

- `/home/patex1987/Documents/programming_kb/patterns/CQRS Lite.md` supports normal current-state tables plus append-only events/outbox before full event sourcing.
- `/home/patex1987/Documents/programming_kb/concepts/Event Sourcing.md` warns that full event sourcing adds schema evolution, replay safety, projections, snapshots, privacy, and operational tooling complexity.
- `/home/patex1987/Documents/programming_kb/patterns/Idempotent Consumer.md` says stable event ids matter before duplicate-safe projectors/workflow consumers.
- `/home/patex1987/Documents/programming_kb/concepts/Context Engineering.md` supports keeping always-loaded guidance small and using skills/indexes for focused context.

External pattern check:

- LangGraph positions durable execution, persistence, streaming, and human-in-the-loop as runtime orchestration capabilities, not as the first user-facing message model: https://docs.langchain.com/oss/python/langgraph/overview.
- Temporal models workflow execution as durable event-history-backed execution, but adopting that runtime now would be premature: https://docs.temporal.io/workflow-execution.
- OpenAI Agents separates application state from tools, handoffs, guardrails, and tracing; this repository should keep application-owned orchestration for now: https://developers.openai.com/api/docs/guides/agents.
- MCP standardizes context/tool boundaries; it is relevant later, not for this first public chat shell: https://modelcontextprotocol.io/specification/2025-06-18.

## 5. Requirements and Assumptions

### Confirmed Requirements

- Public product vocabulary is `Dialogue` and `Message`.
- Internal runtime vocabulary is `AgentExecution`.
- Do not reintroduce `Conversation`, `Turn`, or `Run`.
- Issue #1 proves a chat shell with deterministic fake execution, not real LLM calls.
- Same-process in-memory runtime is acceptable only if it preserves real CP/DP abstractions.
- Public frontend clients must not create or depend on `AgentExecution`.
- Normal frontend support handle is `message_id`, not `agent_execution_id`.
- Structured correlation is required now; full tracing/Grafana integration is a follow-up that should reuse the existing observability branch.
- Internal CP/DP events need a real minimal versioned contract now.
- Domain/shared contracts use dataclasses and standard-library types. API and transport boundaries use Pydantic DTOs and explicit mapping.
- In-memory first; Piccolo/Postgres later.
- Pagination is required even for in-memory APIs.
- Full cleanup of stale docs and terminology is in scope.

### Assumptions

- The first UI will poll HTTP endpoints.
- No public realtime event endpoint ships in issue #1.
- The fake executor returns deterministic text wrapped in a structured output envelope.
- `Dialogue` and `Message` are control-plane product domain objects.
- `AgentExecutionRequest`, `AgentExecutionMessageSnapshot`, `AgentExecutionEvent`, event payloads, and output envelopes are shared `contracts/` types.
- Existing internal `AgentExecutionStatusCode.CREATED` and `ENQUEUED` stay as-is.
- `user_id` is acceptable operational correlation metadata in internal events/logs. Do not include username, email, roles, or full auth claims.

### Open Questions

- Public `MessageDto` references are deferred. References exist internally in the execution output envelope, but public rendering/resolution semantics need a later design.
- Production DI can remain incomplete if the current production agent-execution registrar is already incomplete, but the local/dev/test composition must work.

## 6. Design Decisions From Q&A

### Product Outcome

Issue #1 proves the chat shell, not LLM quality:

```text
client creates Dialogue
client posts user Message
control plane creates pending assistant Message
control plane creates and dispatches AgentExecution
data plane claims and executes deterministic fake executor
data plane emits internal events and terminal result
control plane completion handler updates assistant Message projection
client polls assistant Message by id
```

### Control Plane / Data Plane Boundary

Use store + dispatcher + work-notification + event-log boundaries, expressed as ports:

- `AgentExecutionControlService`
  - Internal control-plane application service.
  - Creates execution records.
  - Records cancellation intent.
  - Dispatches/wakes data plane through a dispatcher port.
- `AgentExecutionDispatcher`
  - CP -> DP intent port.
  - Methods:
    - `dispatch_execution(agent_execution_id) -> None`
    - `notify_cancellation_requested(agent_execution_id) -> None`
  - Methods return `None` and raise on failure.
- `AgentExecutionWorkNotifications`
  - DP-facing wait port.
  - Method:
    - `wait_for_work() -> None`
  - Returns only a wake signal. Worker ownership still comes from the processing store claim/lease.
- `AgentExecutionIntakeStore`
  - CP-side execution creation/cancellation-intent store.
- `AgentExecutionProcessingStore`
  - DP-side claim/heartbeat/terminal-state store.
- `AgentExecutionEventLog`
  - DP -> CP/internal facts and progress log.

The same local in-memory adapter/runtime can implement both directional notification ports using a shared `asyncio.Event`, but services must depend on the directional protocols, not the local primitive.

Follow-up tech debt:

- Once CP -> DP commands expand beyond dispatch/cancel/resume/retry, replace method calls with typed command messages.
- Add DB+Rabbit/SQS adapter.
- Evaluate Temporal adapter after runtime semantics are clearer.

### Event-Driven Completion Without Full Event Sourcing

This issue does not implement full event sourcing. It implements versioned internal integration events.

Current state remains in normal stores. DP emits facts such as `agent_execution.completed`; a CP-side completion handler updates the assistant message display projection.

Use the term `AssistantMessageCompletionHandler` in implementation to avoid implying a full event-sourcing projector.

### Public API Boundary

Public frontend API is dialogue/message-only. Remove public direct execution routes:

- Remove public `POST /api/v1/agent/agent-executions`.
- Remove public `GET /api/v1/agent/agent-executions/{agent_execution_id}`.
- Remove public `GET /api/v1/agent/agent-executions/{agent_execution_id}/events`.
- Remove public `POST /api/v1/agent/agent-executions/{agent_execution_id}/cancel`.

Reuse internal services, stores, event log, transition policy, worker, and executor functionality where useful.

Potential future admin/internal/debug APIs should be designed separately with explicit authz and route namespace. Do not keep accidental public routes for debug convenience.

### Message Graph

- Public clients create only user messages.
- Backend creates assistant placeholders/results.
- Posting a user message returns `created_messages`, ordered by `sequence_nr ASC`.
- Assistant messages have `parent_message_id = user_message.id`.
- Every message has its own per-dialogue increasing `sequence_nr`.
- Sequence numbers must be monotonic/increasing but do not need to be gapless.
- Regenerate/recreate is modeled by parent links but not implemented in issue #1.
- No `attempt_nr` now. Add it when regenerate is implemented if needed.

### Active Response Rule

For issue #1, one active assistant response per dialogue is allowed.

Active means:

- assistant status is `pending` or `streaming`, or
- `cancel_requested` is true and the message is not terminal.

If a client posts another user message while there is an active response in the dialogue, return `409 Conflict` with structured error code `dialogue_has_active_response`.

The dialogue remains blocked after cancellation is requested until the assistant message becomes terminal (`completed`, `failed`, or `cancelled`).

Failed assistant messages unblock the dialogue. Regenerate is a follow-up.

### Output And Message Projection

`AgentExecution` result is canonical for execution output. `Message` stores a display projection.

The internal execution output envelope lives in `contracts/` and uses dataclasses:

- `AgentExecutionOutput`
- `AgentExecutionOutputKind` as `StrEnum`, initially only `message`.
- `AgentExecutionOutputPart`
- `AgentExecutionOutputPartType` as `StrEnum`, initially only `text`.
- `AgentExecutionReference`, generic/minimal now.

The fake executor returns a structured message output with one text part and `references=[]`.

Assistant `Message` projection stores:

- `status`
- `cancel_requested`
- `content_text`
- `error`
- internal `agent_execution_id`

Public `MessageDto` is display-oriented for issue #1 and does not expose internal references or `agent_execution_id`.

### History Snapshot

Issue #1 uses a minimal typed history snapshot, not provider-shaped messages and not raw `list[str]`.

Shared contract:

```python
@dataclass(frozen=True)
class AgentExecutionMessageSnapshot:
    role: MessageRole
    content_text: str
    sequence_nr: int
```

History rules for this slice:

- Ordered by `sequence_nr`.
- Include prior user messages.
- Include completed assistant messages with `content_text`.
- Include the current user message.
- Exclude the pending assistant placeholder.
- Exclude failed/cancelled assistant messages for now.

Follow-up: `ContextAssemblyService` for compaction, summarization, memory, retrieval, loaded skills/tools tracking, prompt assembly, and context budget accounting. Future context policy may include safe summaries of failures/cancellations so the agent can avoid repeating mistakes.

### Observability

Do structured correlation now, full tracing later.

Correlation fields to propagate where known:

- `request_id`
- `user_id`
- `dialogue_id`
- `user_message_id`
- `assistant_message_id`
- `message_id`
- `agent_execution_id`
- `event_id`
- `worker_id`
- `causation_event_id`

The frontend/customer reports `message_id`. On-call can correlate `message_id -> agent_execution_id -> event_id/logs`.

Follow-up: inspect/merge the existing observability branch and local Grafana stack instead of inventing a parallel tracing model.

### Idempotency, Audit, Tools

Do not implement idempotency, audit log, or tools in issue #1.

Document follow-ups:

- Idempotent `POST /dialogues/{id}/messages`.
- Tool `call_id`.
- Mutating tool-call dedupe.
- Stored tool results.
- Retry/resume behavior.
- Compensation/revert strategy for non-idempotent side effects.
- Dedicated audit log before shell/filesystem/tool execution becomes user-facing.

Use `agent-inspiration` later to research `idempotency`, `tool-calling`, `tool-approval`, `reverting-tool-call`, and `audit-log` patterns from the local index.

## 7. Proposed Design

### High-Level Application Design

```text
Client / simple UI
  |
  v
FastAPI public dialogue/message routes
  - Pydantic DTO validation
  - authenticated user extraction
  - DTO/domain mapping
  - structured HTTP errors
  |
  v
Control-plane services
  - DialogueService
  - AgentExecutionControlService
  - AssistantMessageCompletionHandler
  |
  v
Control-plane domain and ports
  - Dialogue
  - Message
  - DialogueStore
  - MessageStore
  - AgentExecutionIntakeStore
  - AgentExecutionDispatcher
  |
  v
Shared contracts
  - AgentExecutionRequest
  - AgentExecutionMessageSnapshot
  - AgentExecutionOutput
  - AgentExecutionEvent
  - versioned payload dataclasses
  |
  v
Local runtime adapters
  - in-memory dialogue/message stores
  - in-memory agent execution stores
  - in-memory dispatcher/work notifications
  - in-memory event log
  |
  v
Data-plane worker
  - waits for work notification
  - claims from processing store
  - emits claimed/started/progress/completed events
  - runs deterministic fake executor
  - sets terminal execution state
  - invokes completion handler through internal port
```

### Durable Docs To Add

Add these architecture documents during implementation:

- `docs/architecture/agent-control-data-plane.md`
  - product API surface
  - control-plane responsibilities
  - data-plane responsibilities
  - shared contracts
  - dispatcher/work-notification boundaries
  - event boundary
  - local in-memory runtime vs future DB+broker/SQS/Temporal adapters
  - observability/correlation expectations
- `docs/architecture/event-schema-evolution.md`
  - event identity is `event_type + schema_version`
  - backward-compatible payload additions keep the same version
  - breaking payload changes create a new schema version
  - handlers branch on `event_type + schema_version`
  - producers must not silently change existing event shapes
  - no upcasters in issue #1
  - follow-up upcaster/compatibility layer once persisted old events or long-lived consumers exist
- `docs/architecture/agent-execution-events.md`
  - issue #1 internal event catalog
  - payload dataclasses
  - serialized JSON-compatible examples
  - prominent warning that these are internal CP/DP integration events, not public/client events

### Domain Model

Control-plane product domain under `llm_agent/llm_agent/domain/dialogue/`.

`Dialogue`:

- `id: UUID`
- `user_id: str`
- `title: str | None`
- `metadata: dict[str, str | int | float | bool | None]`
- `next_message_sequence_nr: int`
- `created_at: datetime`
- `updated_at: datetime`

Validation:

- `title`: optional, trimmed, max 200 chars.
- `metadata`: optional, default `{}`.
- metadata values are primitive JSON values only.
- metadata max 20 keys.
- metadata key max 64 chars.
- metadata string value max 500 chars.

`Message`:

- `id: UUID`
- `dialogue_id: UUID`
- `user_id: str`
- `sequence_nr: int`
- `role: MessageRole`
- `content_text: str`
- `status: AssistantMessageStatus | None`
- `cancel_requested: bool`
- `error: MessageError | None`
- `parent_message_id: UUID | None`
- `agent_execution_id: UUID | None` (internal only, not public DTO)
- `created_at: datetime`
- `updated_at: datetime`

Enums use `StrEnum`:

- `MessageRole.USER = "user"`
- `MessageRole.ASSISTANT = "assistant"`
- `AssistantMessageStatus.PENDING = "pending"`
- `AssistantMessageStatus.STREAMING = "streaming"`
- `AssistantMessageStatus.COMPLETED = "completed"`
- `AssistantMessageStatus.FAILED = "failed"`
- `AssistantMessageStatus.CANCELLED = "cancelled"`

Message error object:

```json
{
  "code": "execution_failed",
  "message": "The assistant response failed.",
  "retryable": true
}
```

Failure/cancellation display rules:

- Failed/cancelled messages keep `content_text` empty in issue #1.
- UI renders from `status` and `error`.
- Completed messages use final output only; no partial/progressive content projection in issue #1.

### Store Protocols

Control-plane store protocols should be query-aware enough for future DB adapters.

`DialogueStore`:

- `create(dialogue: Dialogue) -> Dialogue`
- `get(dialogue_id: UUID) -> Dialogue`
- `list_for_user(user_id: str, *, cursor: str | None, limit: int) -> Page[Dialogue]`
- `touch(dialogue_id: UUID, updated_at: datetime) -> Dialogue`
- future follow-up: update title/metadata

`MessageStore`:

- `create_pair(...)` or a service-level sequence allocation operation that creates the user/assistant pair with adjacent sequence numbers under a lock.
- `get(dialogue_id: UUID, message_id: UUID) -> Message`
- `list_for_dialogue(dialogue_id: UUID, *, after_sequence_nr: int | None, limit: int) -> Page[Message]`
- `find_active_assistant_for_dialogue(dialogue_id: UUID) -> Message | None`
- `find_by_agent_execution_id(agent_execution_id: UUID) -> Message | None`
- `link_agent_execution(assistant_message_id: UUID, agent_execution_id: UUID) -> Message`
- `mark_cancel_requested(assistant_message_id: UUID) -> Message`
- `complete_assistant_message(...) -> Message`
- `fail_assistant_message(...) -> Message`
- `cancel_assistant_message(...) -> Message`

In-memory sequence allocation:

- Use a lock.
- Allocate increasing per-dialogue `sequence_nr`.
- Gaps are acceptable.

Future DB allocation:

- Use transaction plus row lock or optimistic update on dialogue sequence state.
- Insert messages in same transaction.
- Retry on conflict.
- Do not expose entity version publicly until client concurrency requires it.

### AgentExecution Control Service

Rename/refine `BackendAgentExecutionService` to `AgentExecutionControlService`.

Responsibilities:

- Create internal `AgentExecution` records.
- Append creation/enqueue events.
- Dispatch execution through `AgentExecutionDispatcher`.
- Record cancellation intent.
- Dispatch/wake DP on cancellation.
- Provide internal status/event access for handlers/tests, not public REST resources.

`DialogueService.post_user_message(...)` flow:

1. Load dialogue and enforce `dialogue.user_id == authenticated_user_id`.
2. Check no active assistant response exists.
3. Validate user `content`.
4. Create user message.
5. Create pending assistant message with `parent_message_id = user_message.id`.
6. Build typed history snapshots from prior relevant messages plus current user message, excluding the pending assistant placeholder.
7. Call `AgentExecutionControlService.start_execution(...)`.
8. Link assistant message to the created internal `agent_execution_id`.
9. Return `created_messages` ordered by `sequence_nr ASC`.

If execution creation/dispatch fails after the assistant placeholder exists:

- Mark assistant message failed with a safe error.
- Log correlation fields.
- Return a non-2xx structured error, likely `503 Service Unavailable` if dispatch dependency is unavailable or `500` for unexpected failure.
- Future DB implementation may replace this with a stronger unit-of-work/outbox retry design.

### Cancellation Flow

Public cancellation route:

```http
POST /api/v1/agent/dialogues/{dialogue_id}/messages/{assistant_message_id}:cancel
```

Service checks:

- dialogue exists and belongs to user
- message exists under that dialogue
- message role is assistant
- message is cancellable or already terminal

Behavior:

- pending/streaming and not cancel requested: record intent, set `cancel_requested=true`, append `agent_execution.cancel_requested`, call dispatcher, return `202 Accepted`.
- already cancel requested: return `200 OK` with current message.
- already terminal: return `200 OK` with current message.
- user-message cancel attempt: return `409 Conflict` with error code `message_not_cancellable`.

Cancellation remains cooperative. The dialogue remains blocked until the assistant message reaches terminal `cancelled`, `failed`, or `completed`.

### Assistant Message Completion Handler

The data plane emits terminal internal events and sets terminal execution state. The CP-side completion handler updates the assistant message display projection.

Behavior:

- `agent_execution.completed`: extract display text from structured `AgentExecutionOutput`; set assistant status `completed`; set `content_text`; set `cancel_requested=false`.
- `agent_execution.failed`: set assistant status `failed`; store safe structured error; keep `content_text=""`.
- `agent_execution.cancelled`: set assistant status `cancelled`; keep `content_text=""`; clear/keep `cancel_requested` according to DTO contract. Prefer keeping `cancel_requested=true` as historical intent unless this complicates UI; document actual behavior.
- update `Dialogue.updated_at` on visible message changes.

The handler may bypass user-facing ownership checks because it is internal DP -> CP handling. It should update by `assistant_message_id` and sanity-check `dialogue_id` / `user_id` when available in event metadata.

### Event Contract

Event envelope:

- `event_id: UUID`
- `event_type: AgentExecutionEventType` (`StrEnum`)
- `schema_version: int`
- `agent_execution_id: UUID`
- `sequence_nr: int`
- `occurred_at: datetime` (timezone-aware UTC)
- optional `request_id: str | None`
- optional `user_id: str | None`
- optional `dialogue_id: UUID | None`
- optional `user_message_id: UUID | None`
- optional `assistant_message_id: UUID | None`
- optional `worker_id: str | None`
- optional `causation_event_id: UUID | None`
- `payload: typed dataclass`

Keep `sequence_nr` naming.

Event types use `StrEnum` and past-tense/fact names:

- `agent_execution.created`
- `agent_execution.enqueued`
- `agent_execution.claimed`
- `agent_execution.started`
- `agent_execution.progress_reported`
- `agent_execution.completed`
- `agent_execution.failed`
- `agent_execution.cancel_requested`
- `agent_execution.cancelled`

Every catalog event has a named payload dataclass, including empty payloads:

- `AgentExecutionCreatedPayload`
- `AgentExecutionEnqueuedPayload`
- `AgentExecutionClaimedPayload`
- `AgentExecutionStartedPayload`
- `AgentExecutionProgressReportedPayload`
- `AgentExecutionCompletedPayload`
- `AgentExecutionFailedPayload`
- `AgentExecutionCancelRequestedPayload`
- `AgentExecutionCancelledPayload`

The in-memory event log stores typed dataclass events/payloads. Docs/tests should define the JSON-compatible serialized shape, but full broker/DB serializer/deserializer can wait.

Internal execution events are not public client events. A future public dialogue/message event stream must transform internal events into a client-safe contract.

### Worker And Fake Executor

- Worker waits on `AgentExecutionWorkNotifications`.
- Worker claims execution through `AgentExecutionProcessingStore`.
- Processing store emits/records `agent_execution.claimed`.
- Worker emits `agent_execution.started` immediately before invoking the executor.
- Instant deterministic fake executor supports fast happy-path tests.
- Controlled/delayed fake executor supports pending/running/cancel/progress tests.
- Controlled fake may emit `agent_execution.progress_reported` with simple payload, e.g. `{"message": "..."}`.
- No LLM calls and no model-client port in this issue.

### API Shape

All public routes remain under `/api/v1/agent` for issue #1.

Create `llm_agent/llm_agent/api/http/v1/routes/dialogues.py`.

Remove old public execution route module if empty. Do not keep stale commented/deprecated routes.

Public routes:

```http
POST /api/v1/agent/dialogues
GET  /api/v1/agent/dialogues?cursor={cursor}&limit={limit}
GET  /api/v1/agent/dialogues/{dialogue_id}

POST /api/v1/agent/dialogues/{dialogue_id}/messages
GET  /api/v1/agent/dialogues/{dialogue_id}/messages?after_sequence_nr={sequence_nr}&limit={limit}
GET  /api/v1/agent/dialogues/{dialogue_id}/messages/{message_id}

POST /api/v1/agent/dialogues/{dialogue_id}/messages/{assistant_message_id}:cancel
```

Do not expose `GET /dialogues/{dialogue_id}/events` in issue #1. Document it as a follow-up only.

### API DTOs

Public DTO IDs use resource-specific field names:

- `dialogue_id`
- `message_id`
- `parent_message_id`

Internal dataclasses use `id`.

Raw UUIDs are fine for issue #1. Follow-up: stronger typed IDs, prefixed IDs, or wrappers if needed.

`DialogueDto`:

- `dialogue_id`
- `title`
- `metadata`
- `created_at`
- `updated_at`

`CreateDialogueRequestDto`:

- optional `title`
- optional constrained `metadata`

`MessageDto`:

- `message_id`
- `dialogue_id`
- `parent_message_id`
- `sequence_nr`
- `role`
- `status`
- `cancel_requested`
- `content_text`
- `error`
- `created_at`
- `updated_at`

No public `agent_execution_id` in `MessageDto`.

`CreateUserMessageRequestDto`:

- `content: str`
- no role field; public client calls create user messages only

User message validation:

- reject whitespace-only content
- max content length: 8,000 characters
- use named constants so this can become configuration later

Create-message response:

```json
{
  "created_messages": [
    { "role": "user" },
    { "role": "assistant", "status": "pending" }
  ]
}
```

`created_messages` order is `sequence_nr ASC`.

Collection response:

```json
{
  "items": [],
  "limit": 50,
  "next_cursor": null,
  "has_more": false
}
```

Pagination:

- default limit: 50
- max limit: 100
- dialogue listing ordered by `created_at DESC`
- dialogue listing uses opaque `cursor`
- messages ordered by `sequence_nr ASC`
- message listing uses explicit `after_sequence_nr`
- no `parent_message_id` or role filter in issue #1

`Dialogue.updated_at` exists and updates on visible dialogue changes, even though list ordering is by `created_at`.

### API Status Codes

- `POST /dialogues`: `201 Created`, returns bare `DialogueDto`.
- `GET /dialogues`: `200 OK`, returns paginated dialogue collection.
- `GET /dialogues/{dialogue_id}`: `200 OK`, returns dialogue only.
- `POST /dialogues/{dialogue_id}/messages`: `201 Created`, returns `created_messages`.
- `GET /dialogues/{dialogue_id}/messages`: `200 OK`, returns paginated messages.
- `GET /dialogues/{dialogue_id}/messages/{message_id}`: `200 OK`, returns `MessageDto`.
- `POST /dialogues/{dialogue_id}/messages/{assistant_message_id}:cancel`:
  - `202 Accepted` when a new cancel intent is accepted
  - `200 OK` if already cancel requested or already terminal
  - `409 Conflict` if message is not cancellable

Location headers are nice-to-have, not a done criterion.

### API Errors

Use a consistent structured error envelope for new dialogue/message APIs only:

```json
{
  "error": "dialogue_has_active_response",
  "message": "The dialogue already has an assistant response in progress.",
  "details": {}
}
```

Public-safe details are allowed. Do not include `agent_execution_id`.

For active response conflicts, include:

```json
{
  "active_message_id": "...",
  "active_message_status": "pending"
}
```

Non-leaking lookup rules:

- dialogue not found or not owned: `404`
- message not found under dialogue: `404`
- message exists but belongs to another dialogue: `404`

Repo-wide error standardization is a follow-up.

### OpenAPI And Curl Examples

New product routes must include useful OpenAPI summaries, descriptions, response models, and examples. Cancellation docs must explicitly state that cancellation is intent-driven and cooperative.

Update `testing_payloads/http_api_curl.sh` with the new flow:

- create dialogue
- list dialogues
- post user message
- get/list messages
- get a single assistant message for polling
- cancel an assistant message

Remove or update stale job/run/agent-execution examples.

## 8. Alternatives Considered

### Alternative A: Keep Public AgentExecution Endpoints

- Pros: useful for current tests/debugging.
- Cons: leaks internal runtime model to frontend and keeps a confusing product surface.
- Decision: reject. This is not production and no clients depend on those routes. Remove them and test through product APIs or internal services.

### Alternative B: Build Real Model Client First

- Pros: more impressive demo response.
- Cons: product envelope, execution events, cancellation, and message projection are not stable yet.
- Decision: reject. Use deterministic fake executor now.

### Alternative C: Implement Persistence First

- Pros: closer to production.
- Cons: forces schema/transaction decisions before the domain/API shape is proven.
- Decision: reject. In-memory first, protocols shaped for future Piccolo/Postgres.

### Alternative D: Adopt LangGraph, Temporal, Or MCP Now

- Pros: mature runtime/context/tool patterns.
- Cons: runtime choice before stable product and CP/DP boundaries.
- Decision: reject for issue #1. Design ports so these are future adapter/runtime options.

### Alternative E: Full Event Sourcing

- Pros: replay, temporal reconstruction, auditability.
- Cons: too much complexity for the first chat shell.
- Decision: reject. Use versioned internal integration events and current-state stores.

### Alternative F: Allow Concurrent User Messages Per Dialogue

- Pros: more flexible and closer to some advanced agent UIs.
- Cons: requires queueing/interleaving/branch scheduling decisions we do not have yet.
- Decision: reject for issue #1. Enforce one active assistant response per dialogue.

## 9. API / Interface Changes

### Public API

Add:

- `llm_agent/llm_agent/api/http/v1/routes/dialogues.py`
- dialogue/message DTOs and mappers
- structured error DTOs for dialogue/message routes

Remove:

- public `routes/agent.py` execution routes if no longer needed
- public execution DTOs/mappers if no public route uses them

Update router registration accordingly.

### Control-Plane Services

Add:

- `llm_agent/llm_agent/services/dialogue/service.py`
- `llm_agent/llm_agent/services/dialogue/store.py`
- `llm_agent/llm_agent/services/dialogue/message_projector.py`
- `llm_agent/llm_agent/services/dialogue/status_mapping.py` if useful
- `llm_agent/llm_agent/services/agent/control.py` or rename current orchestrator module carefully

Rename/refactor:

- `BackendAgentExecutionService` -> `AgentExecutionControlService`

### Shared Contracts

Keep `contracts/` as the pure shared CP/DP package. It may become a separate pip package later.

Add/refactor:

- `AgentExecutionRequest`
- `AgentExecutionMessageSnapshot`
- `AgentExecutionOutput`
- `AgentExecutionOutputKind`
- `AgentExecutionOutputPart`
- `AgentExecutionOutputPartType`
- `AgentExecutionReference`
- `AgentExecutionEvent`
- `AgentExecutionEventType`
- versioned event payload dataclasses
- `AgentExecutionDispatcher`
- `AgentExecutionWorkNotifications`

Remove/replace:

- `AgentExecutionSignalQueue` terminology and contract

Rules:

- `contracts/` must not import FastAPI, Pydantic, Piccolo, `svcs`, or concrete runtime adapters.
- Use standard library, dataclasses, typing, and enums unless there is a strong reason.

### Local Runtime

Extend `InMemoryRuntime` as the local infrastructure aggregate. It may hold:

- execution state
- event log
- dialogue/message in-memory state
- shared notification primitive used by dispatcher/work-notification adapters

Business services must not depend on `InMemoryRuntime` directly.

Add:

- `llm_agent/local_runtime/agent_execution_dispatcher/`
- `llm_agent/local_runtime/dialogue_store/`
- `llm_agent/local_runtime/message_store/` or combined dialogue/message store adapter if simpler

## 10. Data Model / Persistence Changes

No durable database changes in issue #1.

In-memory state:

- `dict[UUID, Dialogue]`
- `dict[UUID, Message]`
- per-dialogue ordered message index
- `agent_execution_id -> assistant_message_id` lookup
- notification state in `InMemoryRuntime`

Likely future persistence:

- `dialogues`
- `messages`
- `agent_executions`
- `agent_execution_events`
- `agent_execution_results`
- `idempotency_keys`
- later read models for dialogue list previews, latest message, active response, branch/tree traversal

Future DB concerns:

- sequence allocation transaction/locking/OCC
- efficient dialogue listing by `created_at DESC`
- efficient message listing by `(dialogue_id, sequence_nr)`
- parent/child branch queries
- one-active-response invariant under concurrency

## 11. Security, Privacy, and Abuse Considerations

- Public services enforce `dialogue.user_id == authenticated_user_id`.
- Do not trust client-supplied user identity.
- Return non-leaking `404` for not-owned/missing scoped resources.
- Public DTOs do not expose `agent_execution_id`.
- Public events are not exposed in issue #1.
- Internal events include `user_id` for operational correlation but not email, username, roles, tokens, or full auth claims.
- Do not log raw tokens, credentials, secrets, or stack traces in public errors.
- Avoid logging full prompts/history at info level.
- Structured logs/events should include correlation ids.
- No separate audit log yet; add a dedicated audit log before powerful tools, shell commands, filesystem edits, external side effects, or approvals become user-facing.
- No broader org/team/RBAC authz in issue #1. Follow-up: design proper authz model.

## 12. Performance, Scalability, and Reliability Considerations

- In-memory adapters are single-process only, but they must follow production-like boundaries.
- Worker wait notification is only a wake signal; processing store claim/lease remains authoritative.
- Dispatcher failure after creating an assistant placeholder marks that placeholder failed and returns a non-2xx structured error.
- Message listing is paginated from day one.
- Dialogue listing is paginated from day one.
- One-active-response rule avoids unresolved concurrent dialogue execution semantics.
- No new timeout/janitor behavior. Existing execution lease behavior can remain. Follow-up: stuck execution/message janitor.
- Completion handler should be idempotent enough to tolerate duplicate terminal handling.
- Event ids and schema versions are added now to support future idempotent consumers and durable event transport.
- No import-boundary automation now. Follow-up: boundary-hardening checks once package layout settles.

## 13. Implementation Steps

1. Cleanup stale terminology and public route surface
   - Change: remove/update stale `Conversation`, `Turn`, `Run`, job/run public API references that conflict with `Dialogue`, `Message`, `AgentExecution`.
   - Files/modules likely affected:
     - `README.md`
     - `docs/plans/TODO.md`
     - `docs/plans/DEVELOPMENT_PLAN*.md`
     - `llm_agent/docs/DOMAIN_VOCABULARY.md`
     - old route/DTO/mapper files under `llm_agent/llm_agent/api/http/v1/`
     - `testing_payloads/http_api_curl.sh`
   - Notes: cleanup first so implementation agents are not reading stale guidance.
   - Verification: `rg -n "Conversation|Turn|Run|run|job|agent-executions"` reviewed; remaining matches are intentional.

2. Add durable architecture docs
   - Change: add CP/DP architecture doc, event schema evolution doc, and internal event catalog doc.
   - Files/modules likely affected:
     - `docs/architecture/agent-control-data-plane.md`
     - `docs/architecture/event-schema-evolution.md`
     - `docs/architecture/agent-execution-events.md`
     - `docs/README.md`
   - Notes: prominently state internal execution events are not public client events.
   - Verification: docs link to each other and to this plan.

3. Refactor shared CP/DP contracts
   - Change: keep `contracts/` pure; add typed execution request/history/output/event contracts and directional notification ports.
   - Files/modules likely affected:
     - `llm_agent/contracts/domain/agent_executions/`
     - `llm_agent/contracts/services/`
   - Notes: remove/replace `AgentExecutionSignalQueue` with `AgentExecutionDispatcher` and `AgentExecutionWorkNotifications`.
   - Verification: contracts do not import FastAPI/Pydantic/Piccolo/svcs/concrete adapters.

4. Implement minimal versioned event contract
   - Change: add `event_id`, `event_type`, `schema_version`, `occurred_at`, correlation fields, typed payloads, and `StrEnum` event types.
   - Files/modules likely affected:
     - `llm_agent/contracts/domain/agent_executions/event.py`
     - new payload/catalog modules under contracts
     - `llm_agent/local_runtime/event_log/in_memory.py`
   - Notes: in-memory event log stores typed dataclasses.
   - Verification: event contract tests assert type/version/payload shape, sequence ordering, uniqueness, and `after_sequence` behavior.

5. Rename/refactor execution control service
   - Change: replace `BackendAgentExecutionService` naming with `AgentExecutionControlService`; make create+dispatch and cancel-intent+wake explicit.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/services/agent/orchestrator.py` or new `control.py`
     - `llm_agent/llm_agent/services/agent/store.py`
     - DI registrars/fakes
   - Notes: service is internal, not public REST resource service.
   - Verification: service tests cover start execution and cancellation dispatch.

6. Add dialogue/message domain
   - Change: create `Dialogue`, `Message`, enums, safe error object, exceptions, validation constants.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/domain/dialogue/`
   - Notes: use dataclasses and `StrEnum`; raw UUID internally.
   - Verification: unit tests for invariants and validation helpers if implemented.

7. Add in-memory dialogue/message stores and runtime wiring
   - Change: implement in-memory stores with pagination, sequence allocation, active-response lookup, and execution-message linking.
   - Files/modules likely affected:
     - `llm_agent/local_runtime/provider.py`
     - `llm_agent/local_runtime/dialogue_store/`
     - `llm_agent/local_runtime/agent_execution_dispatcher/`
     - DI registrars/fakes
   - Notes: extend `InMemoryRuntime`; services depend on protocols.
   - Verification: store tests for create/get/list/pagination/sequence/finalization/active response.

8. Add DialogueService
   - Change: implement create/get/list/post user message/cancel use cases, ownership checks, active-response rule, history snapshot building.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/services/dialogue/service.py`
     - `llm_agent/llm_agent/services/dialogue/store.py`
     - `llm_agent/llm_agent/services/dialogue/message_projector.py`
   - Notes: public client creates only user messages; assistant placeholder is system-created.
   - Verification: service tests cover ownership, active response conflict, create-message pair, cancel semantics, history snapshots.

9. Wire worker and deterministic fake executors
   - Change: worker waits on `AgentExecutionWorkNotifications`, emits claimed/started/progress/completed events, and invokes the message projector after terminal state.
   - Files/modules likely affected:
     - `llm_agent/agent_execution_worker/in_memory/consumer.py`
     - fake executors under worker/tests
     - processing store
   - Notes: instant fake for happy path; controlled fake for cancellation/progress.
   - Verification: integration tests prove completed/cancelled assistant message projection.

10. Add public dialogue/message API
   - Change: create `routes/dialogues.py`, public DTOs/mappers, structured error responses, OpenAPI examples.
   - Files/modules likely affected:
     - `llm_agent/llm_agent/api/http/v1/routes/dialogues.py`
     - `llm_agent/llm_agent/api/http/v1/dto/`
     - `llm_agent/llm_agent/api/http/v1/mappers/`
     - router registration
   - Notes: remove public direct execution routes. Keep prefix `/api/v1/agent`.
   - Verification: thin integration route tests for success, pagination, polling single message, cancellation, conflicts, and non-leaking 404s.

11. Update curl examples
   - Change: update `testing_payloads/http_api_curl.sh` for the new dialogue/message flow.
   - Files/modules likely affected:
     - `testing_payloads/http_api_curl.sh`
   - Notes: remove/update stale job/run/execution examples.
   - Verification: examples correspond to actual route paths and DTO shapes.

12. Final docs/status pass
   - Change: update `TODO.md`, `DOMAIN_VOCABULARY.md`, stale plans, and README references after behavior is implemented and tests pass.
   - Files/modules likely affected:
     - `docs/plans/TODO.md`
     - `llm_agent/docs/DOMAIN_VOCABULARY.md`
     - `docs/README.md`
     - root `README.md`
   - Notes: mark only actually delivered work as delivered. If `.ai` changes, run `.ai/sync.sh`; otherwise do not sync generated guidance.
   - Verification: docs accurately describe delivered, partial, and follow-up work.

## 14. Testing Strategy

Unit tests:

- event contract and event-log behavior
- output envelope shape
- dialogue/message domain validation
- in-memory dialogue/message stores
- sequence allocation and pagination
- `DialogueService` ownership and active-response rules
- cancellation state mapping
- history snapshot construction
- completion handler behavior

Thin integration/API tests:

- `POST /api/v1/agent/dialogues` returns `201` and `DialogueDto`.
- `GET /api/v1/agent/dialogues` returns paginated collection ordered by `created_at DESC`.
- `GET /api/v1/agent/dialogues/{dialogue_id}` returns dialogue only.
- `POST /api/v1/agent/dialogues/{dialogue_id}/messages` returns `201` and `created_messages`.
- `created_messages` contains user message and pending assistant message ordered by `sequence_nr ASC`.
- `GET /api/v1/agent/dialogues/{dialogue_id}/messages` returns paginated timeline.
- `GET /api/v1/agent/dialogues/{dialogue_id}/messages/{message_id}` returns same `MessageDto` shape and supports polling.
- deterministic fake executor completes assistant message.
- controlled fake supports pending/running/cancel flow.
- active response blocks new user message with `409`.
- after terminal completion/failure/cancellation, new user message is allowed.
- cancellation route returns `202` for new intent, `200` for already requested/terminal.
- cancelling a user message returns `409 message_not_cancellable`.
- not-owned/missing dialogue/message returns non-leaking `404`.
- no public route exposes `agent_execution_id`.
- old public `/agent-executions` routes are gone.

Verification commands:

```bash
cd llm_agent
uv run pytest tests/thin_integration/test_dialogue_message_vertical_slice.py
uv run pytest tests/thin_integration/test_canceled_agent_executions.py
uv run pytest tests/thin_integration/test_checkpoint_cancellation.py
uv run pytest tests/unit
uv run pytest
uv run ruff check .
```

If Ruff is unavailable or not installed in the current environment, record that explicitly.

## 15. Rollout / Migration Plan

This is not a production migration. No public clients depend on the current execution routes.

Implementation order:

1. Cleanup stale docs/routes/DTOs.
2. Add architecture docs and contracts.
3. Refactor internal execution control/dispatcher/event boundary.
4. Add dialogue/message domain and in-memory stores.
5. Add service, worker completion handling, and fake executors.
6. Add public dialogue/message routes.
7. Add/update tests and curl examples.
8. Final docs/status pass.

Rollback:

- Revert the branch changes before merge.
- Since persistence is in-memory only, there is no durable data migration.

The user will handle commits, push, and PR.

## 16. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---:|---:|---|
| PR becomes very large because cleanup is in scope | High | High | Keep changes grouped by cleanup, contracts, services, API, tests, docs. User will subcommit/review. |
| Event contract overbuilds into full event sourcing | Medium | Medium | Keep current-state stores; no upcasters/snapshots/OCC/event-store rewrite. |
| Public API leaks `AgentExecution` internals | High | Medium | Remove public execution routes; hide `agent_execution_id` from DTOs; tests assert absence. |
| In-memory implementation shortcuts around CP/DP boundary | High | Medium | Require dispatcher/work-notification/event-log ports even in same process. |
| Active-response rule races later in DB implementation | Medium | Medium | In-memory lock now; document transaction/locking/OCC follow-up for DB. |
| Completion handler runs twice | Medium | Medium | Make terminal message update idempotent. |
| Stale generated AI guidance after `.ai` edits | Low | Medium | Run `.ai/sync.sh` only if `.ai` changes. |
| Existing observability branch diverges | Medium | Medium | Add structured correlation now; inspect existing observability branch in follow-up before full tracing. |

## 17. Follow-ups

- Public dialogue/message event stream:
  - decide how internal execution events transform into client-safe events
  - likely route: `GET /api/v1/agent/dialogues/{dialogue_id}/events` or SSE equivalent
- Regenerate/recreate:
  - create another assistant attempt under the same user message
  - consider `attempt_nr`
  - branch/tree UI and queries
- Idempotency:
  - `POST /dialogues/{id}/messages`
  - tool `call_id`
  - mutating tool-call dedupe and stored results
  - use `agent-inspiration` to review local reference patterns
- Context assembly:
  - compaction, summarization, memory, retrieval, loaded skills/tools tracking, prompt assembly, context budget accounting
- Model client:
  - provider-agnostic port, streaming, usage accounting, fallback
- Tool system:
  - registry, approvals, permission policy, sandboxing, shell/filesystem safety, reversible operations
- Dedicated audit log:
  - user actions, approvals, tool calls, shell/filesystem operations, retention/access policy
- Persistence:
  - Piccolo/Postgres adapters, transactions, efficient pagination/querying, sequence allocation, event storage
- Runtime adapters:
  - DB+Rabbit/SQS
  - Temporal evaluation after runtime semantics are clearer
- Observability:
  - inspect/merge existing observability branch and local Grafana stack
  - full OpenTelemetry/log-trace correlation
- Contract boundaries:
  - revisit what belongs in `contracts/`
  - audit dependency violations
  - add automated import-boundary checks
  - evaluate `contracts` extraction as pip package
- Stronger ID types:
  - typed IDs, prefixed IDs, or wrappers if needed
- Rich output/reference system:
  - content parts, code/file/domain/artifact/tool references
  - public reference rendering and resolution APIs
- Dialogue title generation and title/metadata update endpoint.
- Delete/archive lifecycle.
- Stuck execution/message janitor and timeout policy.
- Repo-wide structured error standardization.

## 18. Done Criteria

- Stale public execution routes are removed.
- Public API is dialogue/message-only under `/api/v1/agent`.
- `routes/dialogues.py` exposes the agreed endpoints.
- `Dialogue` and `Message` domain models exist with sequence numbers, parent links, status, cancel intent, and safe errors.
- Public DTOs use resource-specific IDs and do not expose `agent_execution_id`.
- `MessageDto` supports polling by single message GET.
- Posting a user message returns `created_messages` with user and pending assistant messages.
- One-active-response-per-dialogue rule is enforced and tested.
- Cancellation is message-scoped, intent-driven, and returns `202` for new intent.
- `AgentExecutionControlService` replaces `BackendAgentExecutionService` naming/role.
- `AgentExecutionDispatcher` and `AgentExecutionWorkNotifications` replace queue terminology.
- Internal event contract has event ids, schema versions, `occurred_at`, correlation fields, event type enum, and typed payload dataclasses.
- Fake executor is deterministic and returns structured output envelope.
- Completion handler updates assistant message projection from terminal execution results/events.
- In-memory runtime uses real ports/protocols and shared local runtime state.
- New architecture docs are added.
- OpenAPI docs/examples are added for public routes.
- `testing_payloads/http_api_curl.sh` reflects the new demo flow.
- Focused and full pytest pass, or failures are documented.
- Ruff is attempted, or unavailable status is documented.
- `TODO.md` and vocabulary docs accurately mark delivered/partial/follow-up work after implementation.

## 19. Review Checklist

- [ ] Requirements are explicit
- [ ] Non-goals are explicit
- [ ] Existing code conventions were checked
- [ ] Public API does not expose internal execution ids
- [ ] CP/DP directional ports are used even in-memory
- [ ] Event contracts are typed and versioned
- [ ] Internal events are documented as not public client events
- [ ] Security and ownership checks are covered
- [ ] Pagination is implemented for in-memory APIs
- [ ] Active-response invariant is tested
- [ ] Cancellation semantics are documented in OpenAPI
- [ ] Follow-ups are documented
- [ ] Verification commands are recorded

## 20. Handoff Prompt for Implementation Agent

```text
Implement the plan in docs/plans/dialogue-message-vertical-slice.md.

Constraints:
- Stay within the scope of the plan.
- Do not introduce new dependencies unless the plan explicitly allows it.
- Do not make real LLM calls.
- Use Dialogue, Message, and AgentExecution vocabulary. Do not reintroduce Conversation, Turn, or Run.
- Remove public AgentExecution HTTP routes. Reuse internal execution services/stores/events where useful.
- Public API must be Dialogue/Message based and must not expose agent_execution_id.
- Keep contracts pure: no FastAPI, Pydantic, Piccolo, svcs, or concrete adapters in contracts.
- Domain/contracts use dataclasses/StrEnum/typing. API DTOs use Pydantic and explicit mappers.
- Preserve the CP/DP boundary through AgentExecutionDispatcher, AgentExecutionWorkNotifications, stores, and event log even for in-memory same-process mode.
- Update tests, docs, and curl examples described in the plan.
- If implementation reality differs from the plan, stop and update the plan or ask for approval before changing scope.
- Do not commit, push, or open PR. The user will handle git history.

Relevant files/modules:
- docs/plans/dialogue-message-vertical-slice.md
- docs/plans/TODO.md
- docs/architecture/
- llm_agent/docs/DOMAIN_VOCABULARY.md
- testing_payloads/http_api_curl.sh
- llm_agent/llm_agent/api/http/v1/routes/
- llm_agent/llm_agent/api/http/v1/dto/
- llm_agent/llm_agent/api/http/v1/mappers/
- llm_agent/llm_agent/domain/dialogue/
- llm_agent/llm_agent/services/dialogue/
- llm_agent/llm_agent/services/agent/
- llm_agent/contracts/domain/agent_executions/
- llm_agent/contracts/services/
- llm_agent/local_runtime/
- llm_agent/agent_execution_worker/in_memory/
- llm_agent/tests/

Expected verification commands:
- cd llm_agent
- uv run pytest tests/thin_integration/test_dialogue_message_vertical_slice.py
- uv run pytest tests/thin_integration/test_canceled_agent_executions.py
- uv run pytest tests/thin_integration/test_checkpoint_cancellation.py
- uv run pytest tests/unit
- uv run pytest
- uv run ruff check .
```
