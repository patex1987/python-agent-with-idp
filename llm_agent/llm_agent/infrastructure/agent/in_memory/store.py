import asyncio
import uuid
from uuid import UUID

from llm_agent.domain.agent.jobs.entities import JobRequest, EnqueuedJob, JobStatus, JobEvent, JobStatusCode
from llm_agent.services.agent.store import JobStore


class InMemoryJobStore(JobStore):

    def __init__(self):
        self._jobs: dict[uuid.UUID, JobStatus] = {}
        self._events: dict[uuid.UUID, list[JobEvent]] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, job_request: JobRequest) -> EnqueuedJob:
        async with self._lock:
            job_id = uuid.uuid4()
            job_status = JobStatus(
                id=job_id,
                status=JobStatusCode.CREATED,
                progress=None,
                result=None,
                error=None,
            )
            self._jobs[job_id] = job_status
            self._events[job_id] = []
            return EnqueuedJob(id=job_id)

    async def get_status(self, job_id: UUID) -> JobStatus:
        return self._jobs[job_id]
