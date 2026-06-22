# Agent Execution Events

Last reviewed: 2026-06-19

`AgentExecutionEvent` is the internal event stream between execution infrastructure and control-plane projection logic.

## Current Catalog

| Event type | Payload | Producer |
| --- | --- | --- |
| `agent_execution.created` | `AgentExecutionCreatedPayload` | control plane intake store |
| `agent_execution.enqueued` | `AgentExecutionEnqueuedPayload` | control plane intake store |
| `agent_execution.claimed` | `AgentExecutionClaimedPayload` | worker processing store |
| `agent_execution.started` | `AgentExecutionStartedPayload` | worker consumer |
| `agent_execution.progress_reported` | `AgentExecutionProgressReportedPayload` | executor/context |
| `agent_execution.completed` | `AgentExecutionCompletedPayload` | worker processing store |
| `agent_execution.failed` | `AgentExecutionFailedPayload` | worker processing store |
| `agent_execution.cancel_requested` | `AgentExecutionCancelRequestedPayload` | control plane intake store |
| `agent_execution.cancelled` | `AgentExecutionCancelledPayload` | worker processing store |

## Public API Boundary

These events are not returned directly to frontend clients in issue #1. The public API exposes `Dialogue` and `Message` resources. A future streaming API should transform internal events into a client-safe message event stream.
