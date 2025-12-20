from __future__ import annotations

from typing import Protocol
from uuid import UUID

from llm_agent.domain.agent.jobs.claim import ClaimedJob
from llm_agent.domain.agent.jobs.request import JobRequest
from llm_agent.domain.agent.jobs.status import JobStatus
from llm_agent.domain.agent.jobs.event import JobEvent


class JobIntakeStore(Protocol):
    async def create_job(self, job_request: JobRequest) -> JobStatus: ...

    async def get_status(self, job_id: UUID) -> JobStatus: ...

    async def mark_enqueued(self, job_id: UUID) -> None: ...


class JobProcessingStore(Protocol):
    """

    Notes: never expose publicly setting the state to running
    """

    async def claim_job(self, worker_id: str) -> ClaimedJob | None: ...

    async def set_succeeded(self, job_id: UUID, result: dict) -> None: ...

    async def set_failed(self, job_id: UUID, error: str) -> None: ...

    async def append_event(self, evt: JobEvent) -> None: ...

    async def heartbeat(self, job_id: UUID, worker_id: str) -> None: ...
