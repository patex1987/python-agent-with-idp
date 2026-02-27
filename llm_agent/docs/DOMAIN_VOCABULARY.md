# Domain Vocabulary

> **Design Document** — This describes the target domain model and API contracts. Implementation may not yet reflect all concepts.

## Conceptual Hierarchy

```
Conversation
 ├─ Turn (user)
 │    └─ creates Run  ← execution attempt (async)
 ├─ Turn (assistant, pending|streaming|completed|failed|cancelled)
 │    └─ produced by Run (exactly 1:1)
 └─ Run
      ├─ events
      ├─ checkpoints
      ├─ tool calls
      └─ cancellation
```

---

## Definitions

### Conversation
A long-lived logical thread of interaction between a user and the agent. Contains an ordered sequence of turns and supports branching for edit/retry scenarios.

**Properties:**
- `conversation_id` (UUID) — unique identifier
- `created_at` (timestamp) — creation time
- `metadata` (object, optional) — client-defined metadata

### Turn
An immutable message within a conversation. Each turn has an author (`user` or `assistant`) and content. User turns are created directly; assistant turns are produced by Runs.

**Properties:**
- `turn_id` (UUID) — unique identifier
- `conversation_id` (UUID) — parent conversation
- `role` (enum: `user` | `assistant`) — author of the turn
- `content` (string) — message text
- `parent_turn_id` (UUID, optional) — for branching/edit scenarios
- `created_at` (timestamp) — creation time

### Assistant Turn Status
Assistant turns have a lifecycle for polling-based UIs:

| Status | Description |
|--------|-------------|
| `pending` | Run created but not yet started by a worker |
| `streaming` | Worker is actively generating response (optional for SSE) |
| `completed` | Run finished successfully, content available |
| `failed` | Run encountered an error, error details available |
| `cancelled` | User or system cancelled the run |

User turns are always terminal on creation (no status lifecycle).

### Run
A single execution attempt that produces exactly one assistant turn. The central concept for orchestration: async lifecycle management, cancellation, retries/regeneration, and observability via events.

**Run Status Codes (internal):**

| Status | Description |
|--------|-------------|
| `CREATED` | Run record exists, not yet visible to workers |
| `ENQUEUED` | Run eligible for workers, no worker owns it yet |
| `RUNNING` | Worker has claimed run, heartbeat active |
| `SUCCEEDED` | Terminal — result available, immutable |
| `FAILED` | Terminal — error recorded, retry possible via regenerate |
| `CANCELLED` | Terminal — user/system decision, no automatic retry |
| `TIMED_OUT` | Worker lost lease, may transition to `RETRYING` |
| `RETRYING` | System is automatically retrying the run |

**Properties:**
- `run_id` (UUID) — unique identifier
- `assistant_turn_id` (UUID) — the turn this run produces
- `status` (enum) — current status code
- `result` (object, optional) — execution result
- `error` (object, optional) — error details if failed
- `cancel_requested` (boolean) — cancellation intent flag
- `created_at`, `started_at`, `completed_at` (timestamps)

### Regenerate
A user-initiated action that creates a new assistant turn (new attempt) for an existing user turn, backed by a new run. The previous assistant turn remains in history (for potential branching UI).

### Run Event
An append-only log entry recording what happened during execution. Used for UI updates (streaming), debugging, and replay.

**Properties:**
- `sequence_nr` (integer) — monotonic sequence within the run
- `event_type` (string) — e.g., `started`, `tool_call`, `token`, `completed`, `failed`
- `payload` (object) — event-specific data
- `timestamp_utc` (ISO 8601)

### Checkpoint
A well-defined point during execution where cancellation can be detected and progress recorded. Ensures operations complete atomically—no partial state or corruption.

### Tool Call
An interaction with an external tool or function during agent execution. Recorded as events with a unique `call_id` for idempotency.

**Properties:**
- `call_id` (UUID) — unique identifier for idempotency
- `tool_name` (string) — name of the tool invoked
- `arguments` (object) — input parameters
- `result` (object, optional) — tool response
- `status` (enum: `pending` | `completed` | `failed`)

### Cancellation
A two-phase process:
1. **Intent**: User requests cancellation via API, setting `cancel_requested = true`
2. **Detection**: Worker checks flag at next checkpoint and stops gracefully

Not immediate—current step always completes first. This ensures no partial state or data corruption.

---

## API Contracts

### Resource URLs

```
/conversations
/conversations/{conversation_id}
/conversations/{conversation_id}/turns
/conversations/{conversation_id}/turns/{turn_id}
/runs/{run_id}
/runs/{run_id}/events
```

### Custom Actions (Google AIP-136 style)

Custom actions use the `:action` suffix pattern:

```
POST /runs/{run_id}:cancel
POST /turns/{assistant_turn_id}:cancel      # facade for run cancellation
POST /turns/{user_turn_id}:regenerate       # creates new assistant turn + run
```

### Idempotency

For POST operations that create resources, clients SHOULD provide an `Idempotency-Key` header:

```http
POST /conversations/{conversation_id}/turns
Idempotency-Key: client-generated-uuid
Content-Type: application/json

{"role": "user", "content": "What's the weather?"}
```

The server MUST:
- Return the same response for duplicate requests with the same key
- Store idempotency keys for at least 24 hours
- Return `409 Conflict` if the key was used with different request body

---

## Interaction Model (Polling)

### Normal Flow
1. UI creates a `Conversation` via `POST /conversations`
2. UI posts a user `Turn` to `POST /conversations/{conversation_id}/turns`
3. Server creates the user turn, enqueues a `Run`, and creates an assistant `Turn` in `pending` state
4. Server returns: `{ user_turn, assistant_turn, run }`
5. UI polls `GET /conversations/{conversation_id}/turns` (or `GET /runs/{run_id}` for operational status)
6. On completion, server finalizes the assistant turn and UI fetches the updated turns list

### Polling Best Practices

| Approach | When to Use |
|----------|-------------|
| **Exponential backoff** | Start at 500ms, increase to max 5s |
| **ETag / If-None-Match** | Reduce bandwidth, server returns `304 Not Modified` |
| **Long-polling** | Server holds request until change or timeout (30s) |
| **Server-Sent Events** | Real-time streaming for `streaming` status |

### Cancellation Flow
1. UI reads `run_id` from the pending assistant turn (or from the turn creation response)
2. UI requests cancellation via `POST /runs/{run_id}:cancel`
3. Server sets `cancel_requested = true` and returns acknowledgment
4. Worker detects at next checkpoint and exits gracefully
5. Assistant turn transitions to `cancelled`

**Note:** If the run is already terminal when cancel is requested, the server returns success with `"status": "already_terminal"`.

### Failure + Regenerate
1. If a run fails, the assistant turn becomes `failed` with an error code
2. UI can start a new attempt via `POST /turns/{user_turn_id}:regenerate`
3. Server creates a new `pending` assistant turn and a new `Run`
4. Original failed assistant turn remains in history (supports branching UI)

### Example (Weather Question)
```
1. POST /conversations
   → { "conversation_id": "conv-123" }

2. POST /conversations/conv-123/turns
   Idempotency-Key: req-456
   { "role": "user", "content": "What's the weather in Paris?" }
   → {
       "user_turn": { "turn_id": "turn-001", "role": "user", ... },
       "assistant_turn": { "turn_id": "turn-002", "role": "assistant", "status": "pending", ... },
       "run": { "run_id": "run-789", "status": "ENQUEUED", ... }
     }

3. GET /conversations/conv-123/turns
   (poll until assistant_turn.status is terminal)
   → { "turns": [..., { "turn_id": "turn-002", "status": "completed", "content": "..." }] }

4. If user clicks Stop while pending:
   POST /runs/run-789:cancel
   → { "run_id": "run-789", "status": "cancel_requested" }
```

---

## Key Relationships

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│ Conversation│ 1───* │    Turn     │ 1───* │    Run      │
└─────────────┘       └─────────────┘       └─────────────┘
                            │                     │
                      (user turns may        (emits events,
                       have multiple          has checkpoints,
                       assistant turn         makes tool calls)
                       attempts)
```

- A **Conversation** contains many **Turns** (ordered sequence)
- A **user Turn** may have many **assistant Turns** (attempts via regenerate)
- An **assistant Turn** is produced by exactly one **Run** (1:1)
- A **Run** emits many **Events** (append-only log)
- A **Run** may contain many **Tool Calls**
- A **Run** checks **Checkpoints** (cancellation detection points)

---

## Status Mapping (Turn ↔ Run)

| Assistant Turn Status | Run Status Codes |
|----------------------|------------------|
| `pending` | `CREATED`, `ENQUEUED` |
| `streaming` | `RUNNING` (with active token events) |
| `completed` | `SUCCEEDED` |
| `failed` | `FAILED`, `TIMED_OUT` |
| `cancelled` | `CANCELLED` |

The UI typically displays Turn status (user-friendly), while the backend uses Run status codes (operational detail).

---

## Error Responses

All error responses follow RFC 7807 Problem Details:

```json
{
  "type": "https://api.example.com/problems/run-not-found",
  "title": "Run Not Found",
  "status": 404,
  "detail": "Run run-789 does not exist",
  "instance": "/runs/run-789"
}
```

Common error codes:
- `400` — Invalid request (malformed JSON, missing fields)
- `404` — Resource not found
- `409` — Conflict (idempotency key reused with different body)
- `422` — Unprocessable entity (valid JSON but invalid semantics)
- `429` — Rate limited
