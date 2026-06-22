# Development Plan: Event-log-first AgentExecution Orchestration (Cancellation, Multi-worker, Tests)

## North star
Make **AgentExecution state transitions derived from an append-only event log**, with **clear invariants under concurrency** (multi-worker), and **tests that assert those invariants** so "eventually consistent" is a deliberate design choice, not an accident.

## Current state (reviewed 2026-06-15)
- ✅ In-memory AgentExecution event streams exist and are append-only.
- ✅ AgentExecution events have per-AgentExecution `sequence_nr` ordering and UTC timestamps.
- ✅ Cancellation API records intent (`cancel_requested`) and is eventually consistent during execution through heartbeat and checkpoint detection.
- ✅ Workers claim/execute agent executions and emit lifecycle events.
- ✅ Strong pre-claim cancellation exists in the in-memory processing store: if an agent execution is claimable and `cancel_requested=True`, claiming transitions it to `CANCELLED` instead of executing it.
- ✅ Executor boundary is now decoupled from `AgentExecutionProcessingStore`; executors receive `AgentExecutionContext` with cancellation and event-emission capabilities.
- ⚠️ Event metadata is still minimal: no `event_id`, schema version, correlation id, or causation id.
- ⚠️ `AgentExecutionEventLog` exists, but it is not yet an optimistic-concurrency/event-store contract.
- ⚠️ Tests largely assert on status polling and executor test-double state, not on event stream plus folded state.
- ⚠️ Current AgentExecution state is still stored in `_agent_executions`; it is not yet derived entirely from event replay.

---

## Recommended plan (priority order)

### Phase 1 — Lock down the event model (foundation) ⚠️ PARTIAL
- **Add robust event metadata** (do this first):
  - **`seq`**: strictly increasing per `agent_execution_id` stream (ordering + idempotency hooks)
  - **`ts`**: UTC timestamp for observability (not for correctness)
  - **`event_id`**: unique identifier for dedupe / retries
  - **`correlation_id` / `causation_id`**: trace “API request → intent → claim → transition”
- **Write down invariants** (in code/docs):
  - Append-only; never mutate or delete events
  - Ordering is defined by `seq` per stream
  - AgentExecution state is a pure fold (projection) over the stream

**Exit criteria**
- Every event has `event_id`, `agent_execution_id`, `seq`, `ts` (+ optional correlation/causation)
- You can deterministically replay an agent execution stream and derive the same state every time

**Status**
- Delivered: `agent_execution_id`, `sequence_nr`, and UTC timestamp.
- Missing: event id, schema version, correlation/causation metadata, and replay/fold implementation.

---

### Phase 2 — Formalize the internal EventLog contract (so you can swap implementations) ⚠️ PARTIAL
- **Create an internal `EventLog` interface** + **contract tests**:
  - `append(stream_id, expected_version?, events[]) -> AppendResult`
  - `read(stream_id, from_seq=0) -> events`
  - Optional later: `read_all()` / `subscribe()` for projections
- **Pick a concurrency stance explicitly**:
  - Prefer **optimistic concurrency** via `expected_version` (sets you up for persistence)
  - In-memory can still lock internally, but keep the OCC-shaped API

**Exit criteria**
- Contract tests run against the in-memory implementation
- Business logic depends on the interface, not `deque`/dicts

**Status**
- Delivered: `AgentExecutionEventLog` protocol and in-memory implementation hide the internal storage shape.
- Missing: contract tests, `expected_version`, append result semantics, and persistent implementation.

---

### Phase 3 — Decouple the executor: no store mutation from `AgentExecutionExecutor` ✅ DELIVERED
You’re **not wrong**: giving the executor the full store is usually a layering smell.

- **Why it’s a good change**
  - Prevents accidental state transitions from “deep inside” execution logic
  - Makes execution logic easier to test (pure-ish, explicit inputs/outputs)
  - Aligns with event-sourced direction: execution emits events; a coordinator applies transitions

- **What to do instead (recommended seam)**
  - Change `AgentExecutionExecutor.execute(...)` so it **does not receive** `AgentExecutionProcessingStore`
  - Give it only:
    - **cancellation signal** (`AgentExecutionContext` / token)
    - a very small **event sink** (e.g., `AgentExecutionEventLog.append(...)` or `AgentExecutionEventSink.emit(...)`)
    - (optionally) a narrow “artifact/output” port if it needs to write results somewhere
  - Make the **consumer/coordinator** responsible for:
    - `SUCCEEDED` / `FAILED` / `CANCELLED` transitions
    - retries / lease/heartbeat logic

**Exit criteria**
- Executor cannot call `set_succeeded/set_failed/set_cancelled/heartbeat/claim_agent_execution`
- All state transitions happen in one place (consumer/orchestrator) and are reflected in events

---

### Phase 4 — Make tests event-log-first (source of truth)
- Refactor tests to assert on:
  - event sequences (what happened)
  - derived/folded state (what it means)
- Add helpers:
  - `assert_stream(agent_execution_id).has_events([...])`
  - `fold_agent_execution(agent_execution_id)` (projection used by tests)

**Exit criteria**
- Most tests no longer assert internal executor flags; they assert **events + fold**

---

### Phase 5 — Cancellation correctness demo test (the one you described)
- Add a deterministic test that:
  - starts 3 agent executions
  - sets cancellation intent for agent_execution #3
  - asserts agent_execution #3 becomes **CANCELLED only when claimed** (claim is the sync point)
- Assert both:
  - event order (intent before claim; claim leads to cancellation transition)
  - final folded state

**Exit criteria**
- Passes reliably across repeated agent executions

---

### Phase 6 — Multi-worker in-memory executor (stress invariants)
- Implement multi-worker execution that competes to claim agent executions
- Use EventLog OCC (or equivalent) to ensure **only one claim wins**
- Add at least one contention test (many workers, many agent executions):
  - no double-claims
  - no "started twice"
  - cancellation intent respected at claim boundary

**Exit criteria**
- Concurrency invariants hold under load

---

### Phase 7 — Event log: event-sourcing-ready structure (foundation for future)

Prepare the event log infrastructure for future event sourcing adoption, without implementing full event sourcing now.

**What to implement:**
- **Event schema/versioning**: Add event schema version field to events (for future migrations)
- **Event ID and tracing fields**: Add `event_id` (UUID), `correlation_id`, `causation_id` to `AgentExecutionEvent` structure (if not already present)
- **Event type system**: Consider typed event classes (optional, can defer if dict payloads work for now)
- **Global event positioning**: Add global sequence/position tracking (enables cross-stream queries, event store subscriptions)
- **Event store interface extensions**: Extend `EventLog` contract with:
  - Subscription/streaming capabilities (`subscribe(stream_id, from_position)`)
  - Global event stream queries (for cross-agent_execution analytics/debugging)
  - Event replay utilities (read all events for a stream, rebuild state)

**What's missing to be event-sourcing-ready (but NOT implementing now):**
- **Snapshots**: Event sourcing typically uses snapshots for performance (rebuild state from snapshot + events since snapshot)
- **Event schema migrations**: Strategy/tooling for migrating old event schemas to new ones
- **Event store persistence**: Persistent storage (SQL/NoSQL) - see Phase 8
- **Projections/read models**: Separate read models built from events (can be added later as needed)
- **Event upcasting**: Code to transform old event versions to new versions

**Key principle:** Structure the event log so it *can* evolve into full event sourcing, but don't implement event sourcing patterns (snapshots, projections, upcasting) until there's a concrete need. The event log should be the single source of truth for what happened, structured for future event sourcing adoption.

**Exit criteria**
- Event schema includes versioning fields
- Event store interface supports subscriptions/streaming
- Global event positioning available for cross-stream operations
- Documentation explains what's missing for full event sourcing (snapshots, migrations, etc.)

---

### Phase 8 — Reliability & operability (choose what matches roadmap)
- **Idempotency**: retry-safe “submit agent execution” / “cancel intent” (dedupe via `event_id`)
- **Projections**: `AgentExecutionIndex` read model (list/search without scanning all events)
- **Reconciliation/janitor**: detect stuck leases, append compensating events
- **Observability**: metrics/logs around OCC conflicts, append failures, worker throughput
- **Persistence** (later): implement sqlite/postgres-backed EventLog behind the contract

---

## One key decision (affects claim + tests)
Do you want cancellation to be:
- **Strong pre-claim (what you describe today)**: if cancel intent exists before claim wins, then claim must not proceed (agent_execution becomes `CANCELLED` at claim boundary).
- **Strong global**: cancel intent prevents any future claim from winning, even under races (requires OCC/expected-version semantics around claim vs cancel intent).

### Clarification: what “strong” means with running agent executions
Even with “strong pre-claim”, if a cancel arrives after a claim has already won (agent_execution is `RUNNING`), cancellation becomes **cooperative**: the worker observes it via heartbeat/checkpoints and exits at the next checkpoint.

> **Future consideration**: revisit **strong-global claim/cancel race semantics** once you introduce true multi-worker contention (Phase 6) and/or a persisted EventLog. This is where OCC/expected-version (or a single-writer-per-stream guarantee) becomes important to make “cancel always beats claim” a real invariant.
