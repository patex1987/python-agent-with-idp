# Agent Control Plane / Data Plane

Last reviewed: 2026-06-21

This project separates the product-facing control plane from the execution-facing data plane even in the local single-process runtime.

## Boundary

Control plane responsibilities:

- own public `Dialogue` and `Message` APIs
- enforce user ownership and active-response rules
- create user messages and assistant placeholders
- create internal `AgentExecution` requests
- record cancellation intent
- project terminal `AgentExecutionEvent` records back onto assistant messages

Data plane responsibilities:

- wait for execution work notifications
- claim enqueued `AgentExecution` records
- maintain worker leases and heartbeats
- run an `AgentExecutionExecutor`
- emit internal `AgentExecutionEvent` records
- set terminal execution state

`AgentExecution` is internal. Frontend clients should use `message_id` for support reports; operations can correlate that to internal execution IDs through structured logs and stores.

## Local Runtime

The in-memory runtime uses the same shape as future production adapters:

- `AgentExecutionDispatcher`: control plane to data plane wakeups
- `AgentExecutionWorkNotifications`: data plane wait boundary
- `AgentExecutionIntakeStore`: control-plane execution intake
- `AgentExecutionProcessingStore`: worker-side claim and terminal-state updates
- `AgentExecutionEventLog`: append-only internal execution events
- `DialogueStore`: in-memory dialogue/message projection

The current adapter uses shared in-process state and an `asyncio.Event`. Future DB+broker, DB+SQS, or Temporal adapters should implement the same ports rather than changing service code.

## Follow-ups

- Add persistence adapters after the in-memory slice is stable.
- Add a durable outbox/projector worker for assistant message projection,
  including retries, processed-event checkpoints, and repair scans.
- Add import-boundary checks for `contracts/` purity.
- Decide whether client-facing realtime updates should be a transformed public message event stream, not raw internal execution events.
