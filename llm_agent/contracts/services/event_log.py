from typing import Protocol
from uuid import UUID

from contracts.domain.agent_executions.event import AgentExecutionEvent, AgentExecutionEventType
from contracts.domain.agent_executions.payload import AgentExecutionEventPayload


class AgentExecutionEventLog(Protocol):
    """
    Append-only event log for agent executions.
    """

    async def init_agent_execution_stream(self, agent_execution_id: UUID) -> None:
        """
        Create an empty event stream for an agent execution.
        :param agent_execution_id:
        :return:
        """
        ...

    async def append(
        self,
        agent_execution_id: UUID,
        *,
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
    ) -> AgentExecutionEvent:
        """
        Append a new event to the agent execution's stream.

        It must ensure:
        - atomic sequence nr
        - assign a timestamp
        - guarantee ordering

        :param agent_execution_id: Agent execution stream identifier.
        :param event_type: Type of event to append.
        :param payload: Event-specific payload matching the event type.
        :param schema_version: Payload schema version.
        :param request_id: Optional request/correlation identifier.
        :param user_id: Optional user associated with the event.
        :param dialogue_id: Optional dialogue associated with the event.
        :param user_message_id: Optional user message associated with the event.
        :param assistant_message_id: Optional assistant message associated with the event.
        :param worker_id: Optional worker that caused or observed the event.
        :param causation_event_id: Optional event that caused this event.
        :return: The appended event with assigned id, timestamp, and sequence number.
        """
        ...

    async def list(self, agent_execution_id: UUID, *, after_sequence: int | None = None) -> list[AgentExecutionEvent]:
        """
        List all events from the given agent execution after the provided sequence_nr.

        :param agent_execution_id:
        :param after_sequence:
        :return:
        """
        ...
