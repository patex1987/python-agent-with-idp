# Event Schema Evolution

Last reviewed: 2026-06-19

Internal `AgentExecutionEvent` records are versioned integration events, not a public API and not a full event-sourcing commitment.

## Rules

- Event handlers branch on `event_type + schema_version`.
- Backward-compatible payload additions keep the same schema version.
- Breaking payload changes create a new schema version.
- Payloads are typed dataclasses in `contracts/domain/agent_executions/event.py`.
- Empty payloads still have explicit payload dataclasses.
- Raw dictionaries are not the durable event contract.
- Upcasters are not implemented yet.

## Current Envelope

The current event envelope includes:

- `event_id`
- `event_type`
- `schema_version`
- `agent_execution_id`
- `sequence_nr`
- `occurred_at`
- optional correlation fields: `request_id`, `user_id`, `dialogue_id`, `user_message_id`, `assistant_message_id`, `worker_id`, `causation_event_id`
- typed `payload`

## Follow-ups

- Add JSON serialization contract tests once events leave process memory.
- Add expected-version or optimistic append checks before a persistent event log.
- Add upcasters only when there is a real stored-event migration to support.
