# Agent Implementation Status

Last reviewed: 2026-06-21

This page is the current implementation checkpoint for the agent backend. The
active product vocabulary is `Dialogue`, `Message`, and internal
`AgentExecution`.

Detailed follow-up work lives in [follow-ups/](follow-ups/). Keep this document
focused on what is delivered or partially delivered.

## Delivered

- Public dialogue/message API under `/api/v1/agent`:
  - `POST /dialogues`
  - `GET /dialogues`
  - `GET /dialogues/{dialogue_id}`
  - `POST /dialogues/{dialogue_id}/messages`
  - `GET /dialogues/{dialogue_id}/messages`
  - `GET /dialogues/{dialogue_id}/messages/{message_id}`
  - `POST /dialogues/{dialogue_id}/messages/{assistant_message_id}:cancel`
- Public direct `/agent-executions` routes removed.
- `Dialogue` and `Message` domain dataclasses, safe message errors, role/status enums, content validation, and constrained dialogue metadata.
- In-memory dialogue/message store with:
  - per-dialogue sequence numbers
  - `created_at DESC` dialogue pagination with opaque cursor
  - message pagination by `after_sequence_nr`
  - active assistant response blocking
  - internal assistant-message to `AgentExecution` linking
- Internal `AgentExecutionControlService` for create/enqueue/dispatch and cancellation intent.
- Directional CP/DP ports:
  - `AgentExecutionDispatcher`
  - `AgentExecutionWorkNotifications`
- In-memory dispatcher/work notification adapter backed by a shared local runtime signal.
- In-memory worker drains all currently claimable executions after one wake; the
  wake signal remains only a hint and the processing store remains authoritative.
- Versioned internal `AgentExecutionEvent` envelope with typed payload dataclasses and correlation fields.
- Minimal internal event catalog for created, enqueued, claimed, started, progress, completed, failed, cancel requested, and cancelled.
- Structured `AgentExecutionOutput` envelope with text parts and placeholder references.
- Worker projection of terminal execution results onto assistant messages.
- Deterministic fake assistant output for the no-LLM vertical slice.
- Missing JWT tokens map to `401 Authentication failed` instead of `500`.
- Message response DTO role/status fields use OpenAPI-visible enums.
- Minimum unit-test floor for `DialogueService` owner checks, dispatch,
  cancellation intent, and history snapshot behavior.
- Canonical `.ai/` guidance and generated tool guidance now use
  dialogue/message/agent-execution vocabulary instead of stale run/conversation
  examples.
- Thin integration coverage for message creation/completion, pagination, old route removal, assistant cancellation, and checkpoint cancellation.
- Durable architecture notes:
  - [control plane / data plane](../architecture/agent-control-data-plane.md)
  - [event catalog](../architecture/agent-execution-events.md)
  - [event schema evolution](../architecture/event-schema-evolution.md)

## Partially Delivered

- Observability: structured IDs are available in the domain/event contracts, but full log enrichment and tracing correlation still need a dedicated pass.
- Event log: in-memory append-only event streams exist, but durable storage,
  pagination/cursor reads, retention policy, JSON serialization contract tests,
  expected-version writes, and upcasters are follow-ups.
- Message projection: terminal execution events can be replayed by `agent_execution_id` into assistant message state, but there is no durable outbox/projector worker, processed-event checkpoint, global repair scan, or rich structured response/reference projection yet.
- History snapshots: typed snapshots are passed to `AgentExecutionRequest`, but there is no context assembly service, compaction, summarizer, retrieval, memory, or skill/tool inventory yet.
- Cancellation: cooperative cancellation works in-memory. Production-grade stuck-execution cleanup and multi-worker durable leases are not implemented.
- Observability correlation: event/domain contracts have some IDs, but HTTP
  request IDs, worker IDs, event IDs, logs, traces, and metrics are not yet
  consistently joined end to end.
- Cancellation-latency observability: cooperative cancellation exists, but we do
  not yet emit telemetry that separates request-to-observed, checkpoint stop,
  backlog, and terminalization delay.
- In-memory store indexing/scaling: accepted as simple and slow for local/demo
  runtime. Production persistence should provide real indexes and scalable
  query patterns.
- In-memory state/event locking: accepted for local/demo runtime. Production
  persistence must use an explicit transactional state-plus-event boundary
  instead of remote event-log calls while holding application locks.
- Testing strategy: this PR adds a minimum unit-test floor, but the full suite
  still needs a deliberate strategy across unit, thin integration,
  Testcontainers e2e, and system/in-cluster/load tests.

## Follow-Up Catalog

| Priority | Area | Document |
| --- | --- | --- |
| P0 | Current PR hygiene | [p0-current-pr-hygiene.md](follow-ups/p0-current-pr-hygiene.md) |
| P1 | Safety and control-plane hardening | [p1-safety-control-plane-hardening.md](follow-ups/p1-safety-control-plane-hardening.md) |
| P1 | Observability and operations | [p1-observability-operations.md](follow-ups/p1-observability-operations.md) |
| P1 | Persistence and runtime reliability | [p1-persistence-runtime-reliability.md](follow-ups/p1-persistence-runtime-reliability.md) |
| P2 | Agent product capabilities | [p2-agent-product-capabilities.md](follow-ups/p2-agent-product-capabilities.md) |
| P2 | Testing strategy | [p2-testing-strategy.md](follow-ups/p2-testing-strategy.md) |
| P3 | Learning spikes | [p3-learning-spikes.md](follow-ups/p3-learning-spikes.md) |

## Recommended Next Topics

1. Finish P0 current PR hygiene, especially env templates and ignored rendered env files.
2. Pick the first P1 hardening slice before adding real model/tool execution.
3. Keep the no-LLM dialogue/message shell stable while persistence,
   observability, and context assembly are designed.
