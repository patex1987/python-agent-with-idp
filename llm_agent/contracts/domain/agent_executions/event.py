from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from contracts.domain.agent_executions import payload as agent_execution_payloads
from contracts.domain.agent_executions.payload import AgentExecutionEventPayload


class AgentExecutionEventType(StrEnum):
    CREATED = "agent_execution.created"
    ENQUEUED = "agent_execution.enqueued"
    CLAIMED = "agent_execution.claimed"
    STARTED = "agent_execution.started"
    PROGRESS_REPORTED = "agent_execution.progress_reported"
    COMPLETED = "agent_execution.completed"
    FAILED = "agent_execution.failed"
    CANCEL_REQUESTED = "agent_execution.cancel_requested"
    CANCELLED = "agent_execution.cancelled"


_PAYLOAD_TYPE_BY_EVENT_TYPE: dict[AgentExecutionEventType, type[object]] = {
    AgentExecutionEventType.CREATED: agent_execution_payloads.AgentExecutionCreatedPayload,
    AgentExecutionEventType.ENQUEUED: agent_execution_payloads.AgentExecutionEnqueuedPayload,
    AgentExecutionEventType.CLAIMED: agent_execution_payloads.AgentExecutionClaimedPayload,
    AgentExecutionEventType.STARTED: agent_execution_payloads.AgentExecutionStartedPayload,
    AgentExecutionEventType.PROGRESS_REPORTED: agent_execution_payloads.AgentExecutionProgressReportedPayload,
    AgentExecutionEventType.COMPLETED: agent_execution_payloads.AgentExecutionCompletedPayload,
    AgentExecutionEventType.FAILED: agent_execution_payloads.AgentExecutionFailedPayload,
    AgentExecutionEventType.CANCEL_REQUESTED: agent_execution_payloads.AgentExecutionCancelRequestedPayload,
    AgentExecutionEventType.CANCELLED: agent_execution_payloads.AgentExecutionCancelledPayload,
}


@dataclass(frozen=True)
class AgentExecutionEvent:
    """
    Internal integration event emitted by the data plane and consumed by the control plane.
    """

    event_id: UUID
    event_type: AgentExecutionEventType
    schema_version: int
    agent_execution_id: UUID
    sequence_nr: int
    occurred_at: datetime.datetime
    payload: AgentExecutionEventPayload
    request_id: str | None = None
    user_id: str | None = None
    dialogue_id: UUID | None = None
    user_message_id: UUID | None = None
    assistant_message_id: UUID | None = None
    worker_id: str | None = None
    causation_event_id: UUID | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        expected_payload_type = _PAYLOAD_TYPE_BY_EVENT_TYPE[self.event_type]
        if isinstance(self.payload, expected_payload_type):
            return

        raise ValueError(
            f"{self.event_type.value} requires payload {expected_payload_type.__name__}; "
            f"got {type(self.payload).__name__}"
        )


def create_agent_execution_event(
    *,
    agent_execution_id: UUID,
    sequence_nr: int,
    event_type: AgentExecutionEventType,
    payload: AgentExecutionEventPayload,
    schema_version: int = 1,
    request_id: str | None = None,
    user_id: str | None = None,
    dialogue_id: UUID | None = None,
    user_message_id: UUID | None = None,
    assistant_message_id: UUID | None = None,
    worker_id: str | None = None,
    causation_event_id: UUID | None = None,
    metadata: dict[str, str] | None = None,
) -> AgentExecutionEvent:
    return AgentExecutionEvent(
        event_id=uuid.uuid4(),
        event_type=event_type,
        schema_version=schema_version,
        agent_execution_id=agent_execution_id,
        sequence_nr=sequence_nr,
        occurred_at=get_current_utc_timestamp(),
        payload=payload,
        request_id=request_id,
        user_id=user_id,
        dialogue_id=dialogue_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        worker_id=worker_id,
        causation_event_id=causation_event_id,
        metadata=metadata or {},
    )


def get_current_utc_timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
