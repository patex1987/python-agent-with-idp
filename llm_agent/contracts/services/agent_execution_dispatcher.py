from __future__ import annotations

from typing import Protocol
from uuid import UUID


class AgentExecutionDispatcher(Protocol):
    """
    Control-plane port for making prepared executions visible to workers.

    Dispatching is a wake-up signal, not the source of truth. Workers must still
    claim eligible executions from their processing store.
    """

    async def dispatch_execution(self, agent_execution_id: UUID) -> None:
        """
        Notify workers that an execution is ready to be claimed.

        :param agent_execution_id: Prepared agent execution identifier.
        """
        ...

    async def notify_cancellation_requested(self, agent_execution_id: UUID) -> None:
        """
        Wake workers after cancellation intent is recorded.

        :param agent_execution_id: Agent execution whose cancellation was requested.
        """
        ...


class AgentExecutionWorkNotifications(Protocol):
    """
    Worker-facing notification source for execution availability.

    Notifications may be coalesced or lost. Consumers must treat this only as a
    wake hint and drain claimable work from the processing store.
    """

    async def wait_for_work(self, timeout: None | float = None) -> None:
        """
        Wait until work may be available or the optional timeout elapses.

        :param timeout: Optional maximum seconds to wait.
        """
        ...
