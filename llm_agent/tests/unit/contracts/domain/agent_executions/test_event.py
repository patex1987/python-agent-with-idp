from uuid import uuid4

import pytest

from contracts.domain.agent_executions.event import AgentExecutionEventType, create_agent_execution_event
from contracts.domain.agent_executions.output import AgentExecutionOutput
from contracts.domain.agent_executions.payload import (
    AgentExecutionCancelledPayload,
    AgentExecutionCancelRequestedPayload,
    AgentExecutionClaimedPayload,
    AgentExecutionCompletedPayload,
    AgentExecutionCreatedPayload,
    AgentExecutionEnqueuedPayload,
    AgentExecutionFailedPayload,
    AgentExecutionProgressReportedPayload,
    AgentExecutionStartedPayload,
)


@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        (AgentExecutionEventType.CREATED, AgentExecutionCreatedPayload(user_id="user-1")),
        (AgentExecutionEventType.ENQUEUED, AgentExecutionEnqueuedPayload()),
        (AgentExecutionEventType.CLAIMED, AgentExecutionClaimedPayload(worker_id="worker-1")),
        (AgentExecutionEventType.STARTED, AgentExecutionStartedPayload(worker_id="worker-1")),
        (AgentExecutionEventType.PROGRESS_REPORTED, AgentExecutionProgressReportedPayload(message="step complete")),
        (
            AgentExecutionEventType.COMPLETED,
            AgentExecutionCompletedPayload(output=AgentExecutionOutput.from_text("done")),
        ),
        (AgentExecutionEventType.FAILED, AgentExecutionFailedPayload(error="boom")),
        (AgentExecutionEventType.CANCEL_REQUESTED, AgentExecutionCancelRequestedPayload()),
        (AgentExecutionEventType.CANCELLED, AgentExecutionCancelledPayload()),
    ],
)
def test_agent_execution_event_accepts_matching_payload(event_type, payload):
    event = create_agent_execution_event(
        agent_execution_id=uuid4(),
        sequence_nr=1,
        event_type=event_type,
        payload=payload,
    )

    assert event.event_type == event_type
    assert event.payload == payload


def test_agent_execution_event_rejects_mismatched_payload():
    with pytest.raises(
        ValueError,
        match="agent_execution.completed requires payload AgentExecutionCompletedPayload; got AgentExecutionFailedPayload",
    ):
        create_agent_execution_event(
            agent_execution_id=uuid4(),
            sequence_nr=1,
            event_type=AgentExecutionEventType.COMPLETED,
            payload=AgentExecutionFailedPayload(error="boom"),
        )
