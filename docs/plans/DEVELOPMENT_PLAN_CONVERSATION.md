

## 0) Key correction: your orchestrator should not build `JobRequest` with hardcoded user

Right now:

```py
user_id="hardcoded_user_later_take_it_from_context"
```

You already bind `user_id` in middleware (`USER_ID_NAME`). So your route should pass `user_id` into service, and service should not “guess” it.

**Ownership:** API extracts identity, service consumes it.

---

# Phase 1 — Introduce Conversation + Turn (product layer), keep Job (infra) untouched

### New domain entities (Pydantic/dataclass is fine initially)

* `Conversation { id, user_id, created_at, title? }`
* `Turn { id, conversation_id, parent_turn_id?, author: "user"|"assistant", content, created_at }`

### New store interfaces (like your `JobIntakeStore`)

Create:

* `ConversationStore`
* `TurnStore`

In-memory implementations can live next to your local_runtime stores:
`llm_agent/local_runtime/conversations/...`

### New endpoints (keep `/jobs` for now)

* `POST /conversations`
* `POST /conversations/{conversation_id}/turns` (creates a *user* turn)

No workers involved yet. This gets you the history tree model early.

---

# Phase 2 — Introduce Run (execution attempt) + RunEventLog (the testing/UI backbone)

This is the “make everything future-proof” step.

## 2.1 New entities

* `Run { id, conversation_id, assistant_turn_id, status, engine, cancel_requested, created_at, updated_at }`
* `RunStatus`: `QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED, WAITING_HITL`
* `RunEvent { run_id, sequence_nr, event_type, payload, timestamp_utc }`

> Note: keep `cancel_requested` at Run-level (or Job-level). You can keep it on JobStatus for now, but long-term it’s cleaner at Run.

## 2.2 New store interfaces

* `RunIntakeStore` (API-facing; request intent)

  * `create_run(...)`
  * `request_cancel(run_id) -> bool`
  * `get_run(run_id)`
  * `list_run_events(run_id, after=...)`
* `RunProcessingStore` (worker-facing; finalize)

  * `claim_run(worker_id) -> ClaimedRun?`
  * `heartbeat(run_id, worker_id) -> Run` (or just lease renew)
  * `set_succeeded/set_failed/set_cancelled`
  * `append_event(run_id, type, payload) -> RunEvent`

This mirrors your current split (`JobIntakeStore` vs `JobProcessingStore`) perfectly.

## 2.3 API “send message” endpoint (key API)

Add:

* `POST /conversations/{conversation_id}/turns:send`

  1. create user turn
  2. create assistant placeholder turn (empty content)
  3. create run pointing to assistant turn
  4. enqueue run (signal workers)
  5. return `{ conversation_id, user_turn_id, assistant_turn_id, run_id }`

And:

* `GET /runs/{run_id}`
* `GET /runs/{run_id}/events?after=...`

This is the stable contract you’ll keep whether you use Temporal or DB+RMQ.

---

# Phase 3 — Update Worker boundary (important: stop passing JobProcessingStore into executor)

You already concluded heartbeat inside executor was early POC. Correct.

### Replace executor signature

Instead of:

```py
execute(job_id, worker_id, job_store, job_execution_ctx)
```

Move to:

```py
execute(run_id, ctx: RunExecutionContext, port: RunExecutionPort) -> AssistantOutput
```

Where `RunExecutionPort` is a very narrow interface:

* `emit_event(type, payload)`
* `checkpoint(name, payload?)` (emits + checks cancel)
* `request_human_input(...)` (later)
* maybe `read_turn_context(conversation_id/head_turn_id)` or pass snapshot at start

**Consumer owns finalization**:

* if executor returns output → consumer stores assistant turn content + `set_succeeded`
* if executor raises → consumer `set_failed`
* if cancellation observed → consumer `set_cancelled`

✅ This resolves your worry: “executor can do harmful things”.

---

# Phase 4 — Tool calls and HITL (events first, entities later)

## Tool calls = events (recommended)

Emit:

* `tool_call_started { call_id, tool_name, args }`
* `tool_call_result { call_id, ok, result|error }`

This works with:

* LangGraph
* Temporal activities
* DB jobs

**Important:** See "Idempotency" section below for critical TODO about implementing idempotency at the tool layer. This is a foundational requirement that enables safe retries and recovery, regardless of orchestrator choice.

## HITL

* Run enters `WAITING_HITL`
* Event: `human_input_requested { request_id, prompt, schema/options }`
* API endpoint:

  * `POST /runs/{run_id}/resume { request_id, value }`
  * store event + signal worker / workflow

Workers:

* DB+RMQ: “wake up run”
* Temporal: `signalWorkflow`

---

# Phase 5 — Production orchestration options

## Option A: DB + RabbitMQ

* DB is source of truth for Runs + events + lease
* RabbitMQ is wakeup/signal (same as your current in-memory event)

## Option B: Temporal + LangGraph

Two common ways:

### B1 (coarse): Temporal runs “graph as a whole”

Added value:

* durable retries of the whole run
* durable timers / timeouts / signals
* workflow survives worker crash and resumes
* HITL becomes trivial via signals
  Tradeoff:
* if tool calls have side effects, you must enforce idempotency in activities or at tool layer

### B2 (fine): Temporal wraps tool calls as Activities

Added value:

* per-tool retries/timeouts
* better failure isolation
  Tradeoff:
* more wiring / more design

Either way, your **RunEventLog** stays your external truth and UI feed.

---

# Concrete, repo-specific changes I’d do next (in your structure)

## 1) Fix `BackendJobOrchestrationService` user_id plumbing

**Where:** `llm_agent/services/agent/orchestrator.py`
Change `create_job(prompt)` to `create_job(prompt, user_id, history)` and remove hardcoded value.

Then in route, read from request:

* you have `USER_ID_NAME` in `scope["state"]`
* use `request.scope["state"][USER_ID_NAME]`

(You already do this pattern in middleware.)


---

# Idempotency (how to think about it in your app)

### `POST /jobs` and `POST /conversations/{id}/turns:send`

Use an `Idempotency-Key` header:

* store `(user_id, idempotency_key) -> created_job_id/run_id`
* if repeated, return the same created object

This matters because:

* clients retry on network failures
* without it you’ll create duplicate runs

### Cancel endpoint

Your `request_cancellation` is already effectively idempotent:

* first call returns True
* second returns False (“already requested/terminal”)

That’s fine.

### Tool calls

Make every tool call have a `call_id` and treat tool execution as idempotent w.r.t. that call id.

**TODO: Implement idempotency at the tool layer (CRITICAL)**

Idempotency is a **game changer for agentic apps** and must be implemented at the tool layer, **regardless of orchestrator choice** (Temporal, DB-backed, in-memory, etc.).

**Why this matters:**
- Worker crashes and retries will re-execute tool calls
- LangGraph checkpoints + Temporal retries = tool calls can be executed multiple times
- Without idempotency: duplicate API calls, duplicate database writes, duplicate file operations, etc.
- With idempotency: safe retries, safe resumption from checkpoints, safe Temporal activity retries

**Implementation requirement:**
- Every tool call MUST have a unique `call_id` (UUID)
- Tool execution MUST be idempotent: calling the same tool with the same `call_id` + args multiple times produces the same result
- Store tool call results keyed by `call_id` (e.g., in RunEventLog or dedicated cache/store)
- Before executing a tool, check if `call_id` was already executed → return cached result
- This is independent of LangGraph implementation - implement idempotency as part of the tool execution infrastructure

**Key principle:** Idempotency is an architectural requirement at the tool layer, not an optional feature. It enables safe retries and recovery regardless of which orchestration system you use.

Great question — this is exactly the right moment to align the concepts cleanly.

Short answer first, then the detailed mapping:

> **A “run” is the evolution of what your current “job” *really* is.**
> You don’t throw away your job API — you *reframe it* as a lower-level execution primitive and then layer conversations on top.

Since `/v1` is not yet public, you can do this **cleanly and coherently** without version gymnastics.

---

## 1️⃣ What you have today (current mental model)

Right now your API and backend look like this:

```
POST /jobs
→ creates a Job
→ worker executes it
→ job produces a result
```

A **Job** today represents:

* a single prompt
* a single execution
* a single lifecycle
* no higher-level context

That is *already* very close to what most systems would call a **Run**.

So the key insight is:

> **Your current “Job” == a “Run” without a parent.**

---

## 2️⃣ The correct conceptual layering (very important)

Here is the hierarchy you want going forward:

```
Conversation
 ├─ Turn (user)
 ├─ Turn (assistant)
 │    └─ Run  ← execution attempt
 │         ├─ events
 │         ├─ checkpoints
 │         ├─ tool calls
 │         └─ cancellation
```

Key rules:

* **Conversation** = long-lived logical thread
* **Turn** = immutable message in that thread
* **Run** = *one execution attempt* that tries to produce an assistant turn

This maps perfectly to:

* retries
* cancellations
* Temporal workflows
* LangGraph execution
* human-in-the-loop pauses

---

## 3️⃣ How this fits your existing routes (no breaking needed)

### Keep your current routes — but reinterpret them

#### Current

```http
POST /jobs
```

#### New meaning

```text
Create a Conversation (implicit)
Create a User Turn
Create an Assistant Turn placeholder
Create a Run for that assistant turn
Enqueue Run
```

This endpoint becomes a **convenience wrapper** for “single-turn conversations”.

You are not breaking anything — you are *adding structure behind the scenes*.

---

## 4️⃣ New canonical routes (add these to v1)

You add **explicit** routes that expose the hierarchy.

### Conversations

```http
POST   /conversations
GET    /conversations/{conversation_id}
```

### Turns

```http
POST   /conversations/{conversation_id}/turns
GET    /conversations/{conversation_id}/turns
```

> Posting a turn here is always a **user turn**.

### Runs (execution)

```http
POST   /conversations/{conversation_id}/turns/{turn_id}/runs
GET    /runs/{run_id}
POST   /runs/{run_id}/cancel
GET    /runs/{run_id}/events
```

This is where your **current job orchestration logic moves** almost 1:1.

---

## 5️⃣ Where your current Job API fits *exactly*

Let’s map it line by line.

### Today

```http
POST /jobs
```

### Tomorrow (internally)

Equivalent to:

```http
POST /conversations
POST /conversations/{cid}/turns
POST /conversations/{cid}/turns/{assistant_turn_id}/runs
```

But exposed as one call for convenience.

### Today

```http
GET /jobs/{job_id}
```

### Tomorrow

```http
GET /runs/{run_id}
```

Same semantics:

* status
* cancel_requested
* result / error

### Today

```http
POST /jobs/{job_id}/cancel
```

### Tomorrow

```http
POST /runs/{run_id}/cancel
```

Same semantics, same idempotency.

### Today

```http
GET /jobs/{job_id}/events
```

### Tomorrow

```http
GET /runs/{run_id}/events
```

This endpoint becomes **more valuable**, not less.

---

## 6️⃣ What changes in your backend services

### BackendJobOrchestrationService → split responsibilities

You don’t delete it — you *narrow it*.

**Before**

```py
BackendJobOrchestrationService
```

**After**

```text
ConversationService
TurnService
RunOrchestrationService   ← almost your current code
```

`RunOrchestrationService`:

* create run
* request cancellation
* get run
* get run events
* enqueue run (signal queue / Temporal / RMQ)

Your existing logic maps here *extremely well*.

---

## 7️⃣ Why this model survives LangGraph + Temporal

### LangGraph

* A Run = one LangGraph execution
* Graph checkpoints → RunEvents
* Graph state snapshots → stored as events or run metadata
* Tool calls → events

### Temporal

* A Run = one Workflow Execution
* Tool calls = Activities
* Human-in-the-loop = Signals
* Cancellation = Workflow cancel
* Retry = Workflow retry (same Run ID or new Run ID, your choice)

### Important: retries

You now have a choice:

* **Same run_id** → retry attempt counter
* **New run_id** → forked execution (recommended for auditability)

Your current job model does *not* allow this cleanly — Run does.

---

## 8️⃣ Human-in-the-loop and branching (why Run matters)

This is where your “lost” feeling resolves.

Example:

1. User asks question
2. Assistant starts reasoning
3. Requests human confirmation
4. User edits earlier answer
5. Conversation forks

With your new model:

* Fork = new Turn with `parent_turn_id`
* New Run created for that turn
* Old Run remains as historical artifact

Nothing is overwritten.
Everything is replayable.
Everything is auditable.

---

## 9️⃣ Bottom line (the key mental shift)

> **Job was never the right top-level concept.
> Run is.
> Job was just a proto-run.**

Your current system is *already structured well enough* to evolve into this with minimal pain:

* intake vs processing stores ✔
* event logs ✔
* cancellation intent ✔
* worker boundary ✔

You’re not throwing anything away — you’re *naming things correctly* and adding one layer above.

---

