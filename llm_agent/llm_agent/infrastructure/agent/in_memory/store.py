import asyncio
import uuid
from collections import deque
from uuid import UUID

from llm_agent.domain.agent.jobs.entities import JobRequest, EnqueuedJob, JobStatus, JobEvent, JobStatusCode
from llm_agent.services.agent.store import JobStore


class InMemoryApiJobStore(JobStore):
    def __init__(
        self,
        internal_job_storage: dict[UUID, JobStatus],
        internal_event_logs: dict[UUID, deque[JobEvent]],
    ):
        """

        :param internal_job_storage: injectable from the outside, i.e. possible
            to share with the worker
        :param internal_event_logs: something like transactional logs for
            events (append only)
        """
        self._jobs = internal_job_storage
        self._events = internal_event_logs
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
            self._events[job_id] = deque()
            return EnqueuedJob(id=job_id)

    async def get_status(self, job_id: UUID) -> JobStatus:
        return self._jobs[job_id]