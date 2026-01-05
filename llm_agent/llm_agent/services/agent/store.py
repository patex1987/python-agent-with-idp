from __future__ import annotations

from typing import Protocol
from uuid import UUID

from llm_agent.domain.agent.jobs.claim import ClaimedJob
from llm_agent.domain.agent.jobs.request import JobRequest
from llm_agent.domain.agent.jobs.status import JobStatus
from llm_agent.domain.agent.jobs.event import JobEvent
from llm_agent.domain.agent.jobs.status_code import JobStatusCode


class JobIntakeStore(Protocol):
    async def create_job(self, job_request: JobRequest) -> JobStatus: ...

    async def get_status(self, job_id: UUID) -> JobStatus:
        """
        Read only view of the current job status.

        :param job_id:
        :return:
        :raise JobNotFoundError: when the job is not found in the store
        """
        ...

    async def mark_enqueued(self, job_id: UUID) -> None: ...

    async def mark_cancelled(self, job_id: UUID) -> bool:
        """
        Mark job as canceled.

        Returns True if state was changed, False if already terminal.
        """
        ...


class JobProcessingStore(Protocol):
    """
    Job store interface for the processing / consumer side

    - Only JobProcessingStore mutates RUNNING / TIMED_OUT / RETRYING
    - Workers never set RUNNING directly, it can be set only as part
        of the job claiming

    Notes: never expose publicly setting the state to running
    """

    async def claim_job(self, worker_id: str) -> ClaimedJob | None: ...

    async def set_succeeded(self, job_id: UUID, result: dict) -> None: ...

    async def set_failed(self, job_id: UUID, error: str) -> None: ...

    async def append_event(self, evt: JobEvent) -> None: ...

    async def heartbeat(self, job_id: UUID, worker_id: str) -> JobStatusCode:
        """
        Extend the expiration time of a running job claimed by a given worker.

        :param job_id:
        :param worker_id:
        :return:
        :raises: JobLeaseLostError - when the job is claimed by a different worker
        """
        ...

    async def get_status(self, job_id: UUID) -> JobStatus:
        """
        Read only view of the current job status.

        :param job_id:
        :return:
        :raise JobNotFoundError: when the job is not found in the store
        """
        ...
