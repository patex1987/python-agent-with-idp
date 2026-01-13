from __future__ import annotations

from typing import Protocol
from uuid import UUID

from agent_run_worker.domain.runs.claim import ClaimedRun
from contracts.domain.runs.event import RunEvent
from contracts.domain.runs.status import RunStatus
from contracts.services.event_log import RunEventLog


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
