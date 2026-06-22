from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from contracts.domain.agent_executions.output import AgentExecutionOutput


@dataclass(frozen=True)
class AgentExecutionCreatedPayload:
    user_id: str


@dataclass(frozen=True)
class AgentExecutionEnqueuedPayload:
    pass


@dataclass(frozen=True)
class AgentExecutionClaimedPayload:
    worker_id: str


@dataclass(frozen=True)
class AgentExecutionStartedPayload:
    worker_id: str


@dataclass(frozen=True)
class AgentExecutionProgressReportedPayload:
    message: str


@dataclass(frozen=True)
class AgentExecutionCompletedPayload:
    output: AgentExecutionOutput


@dataclass(frozen=True)
class AgentExecutionFailedPayload:
    error: str


@dataclass(frozen=True)
class AgentExecutionCancelRequestedPayload:
    pass


@dataclass(frozen=True)
class AgentExecutionCancelledPayload:
    pass


AgentExecutionEventPayload: TypeAlias = (
    AgentExecutionCreatedPayload
    | AgentExecutionEnqueuedPayload
    | AgentExecutionClaimedPayload
    | AgentExecutionStartedPayload
    | AgentExecutionProgressReportedPayload
    | AgentExecutionCompletedPayload
    | AgentExecutionFailedPayload
    | AgentExecutionCancelRequestedPayload
    | AgentExecutionCancelledPayload
)
"""Closed union of payload dataclasses accepted by agent execution events."""
