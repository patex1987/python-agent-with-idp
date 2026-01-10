from __future__ import annotations

from typing import Protocol
from uuid import UUID

from llm_agent.domain.agent.runs.claim import ClaimedRun
from llm_agent.domain.agent.runs.request import RunRequest
from llm_agent.domain.agent.runs.status import RunStatus
from llm_agent.domain.agent.runs.event import RunEvent


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


class RunProcessingStore(Protocol):
    """
    Run store interface for the processing / consumer side

    - Only RunProcessingStore mutates RUNNING / TIMED_OUT / RETRYING
    - Workers never set RUNNING directly, it can be set only as part
        of the run claiming

    Notes: never expose publicly setting the state to running
    """

    async def claim_run(self, worker_id: str) -> ClaimedRun | None: ...

    async def set_succeeded(self, run_id: UUID, result: dict) -> None: ...

    async def set_failed(self, run_id: UUID, error: str) -> None: ...

    async def set_cancelled(self, run_id: UUID) -> None:
        """
        Sets the run status to cancelled.

        Note: this is not about the intent but setting the actual status.
        :param run_id:
        :return:
        """
        ...

    async def append_event(self, evt: RunEvent) -> None: ...

    async def heartbeat(self, run_id: UUID, worker_id: str) -> RunStatus:
        """
        Extend the expiration time of a running run claimed by a given worker.

        :param run_id:
        :param worker_id:
        :return:
        :raises: RunLeaseLostError - when the run is claimed by a different worker
        """
        ...

    async def get_status(self, run_id: UUID) -> RunStatus:
        """
        Read only view of the current run status.

        :param run_id:
        :return:
        :raise RunNotFoundError: when the run is not found in the store
        """
        ...
