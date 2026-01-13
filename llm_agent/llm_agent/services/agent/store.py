from __future__ import annotations

from typing import Protocol
from uuid import UUID

from llm_agent.domain.agent.runs.request import RunRequest
from contracts.domain.runs.status import RunStatus
from contracts.domain.runs.event import RunEvent


class RunIntakeStore(Protocol):
    """
    Run store interface for the API/intake side.

    TODO: rename to RunControlPlaneStore
    """

    async def create_run(self, run_request: RunRequest) -> RunStatus: ...

    async def get_status(self, run_id: UUID) -> RunStatus:
        """
        Read only view of the current run status.

        :param run_id:
        :return:
        :raise RunNotFoundError: when the run is not found in the store
        """
        ...

    async def mark_enqueued(self, run_id: UUID) -> None: ...

    async def mark_cancelled(self, run_id: UUID) -> bool:
        """
        Mark run as canceled.

        Returns True if state was changed, False if already terminal.
        """
        ...

    async def request_cancellation(self, run_id: UUID) -> bool:
        """
        User expresses an intent to cancel the run.

        :param run_id:
        :return:
        """

    async def get_events(self, run_id: UUID, *, after_sequence: int | None = None) -> list[RunEvent]:
        """
        Retrieve events for a run from the event log.

        :param run_id: The run ID
        :param after_sequence: Optional sequence number to filter events after
        :return: List of run events
        :raises: RunNotFoundError if the run is not found
        :raises: ValueError if event log is not available
        """
        ...
