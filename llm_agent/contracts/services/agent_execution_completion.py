from __future__ import annotations

from typing import Protocol
from uuid import UUID


class AgentExecutionCompletionSink(Protocol):
    async def project_terminal_agent_execution(self, agent_execution_id: UUID) -> None:
        """
        Project terminal execution events into control-plane state.

        :param agent_execution_id: Internal execution id whose terminal event should be projected.
        """
        ...
