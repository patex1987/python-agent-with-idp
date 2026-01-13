# Domain Vocabulary

## Conceptual Hierarchy

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

---

## Definitions

### Conversation
A long-lived logical thread of interaction between a user and the agent. Contains an ordered sequence of turns and supports branching for edit/retry scenarios.

### Turn
An immutable message within a conversation. Each turn has an author (`user` or `assistant`) and content. User turns are created directly; assistant turns are produced by Runs.

### Run
A single execution attempt that produces an assistant turn. The central concept for orchestration—supports lifecycle management, cancellation, retries, and observability via events.

### Run Event
An append-only log entry recording what happened during execution. Used for UI updates, debugging, and replay. Each event has a sequence number and timestamp.

### Checkpoint
A well-defined point during execution where cancellation can be detected and progress recorded. Ensures operations complete atomically—no partial state or corruption.

### Tool Call
An interaction with an external tool or function during agent execution. Recorded as events with a unique `call_id` for idempotency.

### Cancellation
A two-phase process: (1) user requests intent via API, (2) worker detects at next checkpoint and stops gracefully. Not immediate—current step always completes first.

---

## Key Relationships

- A **Conversation** contains many **Turns**
- An **assistant Turn** is produced by exactly one **Run**
- A **Run** emits many **Events**
- A **Run** may contain many **Tool Calls**
- A **Run** checks **Checkpoints**
