import asyncio
import datetime
import uuid
from collections import deque
from typing import Any
from uuid import UUID

import structlog

from llm_agent.domain.agent.jobs.entities import JobRequest, EnqueuedJob, JobStatus, JobEvent, JobStatusCode, ClaimedJob
from llm_agent.services.agent.store import JobIntakeStore, JobProcessingStore
from llm_agent.services.agent.transition_policy import JobTransitionPolicy


logger = structlog.getLogger(__name__)


class InMemoryJobIntakeStore(JobIntakeStore):
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
        # TODO: DI
        self.job_transition_policy = JobTransitionPolicy()

    async def create_job(self, job_request: JobRequest) -> EnqueuedJob:
        """

        :param job_request:
        :return:

        TODO: change return type.
        """
        async with self._lock:
            job_id = uuid.uuid4()
            job_status = JobStatus(
                id=job_id,
                status=JobStatusCode.CREATED,
                result=None,
                error=None,
            )
            self._jobs[job_id] = job_status
            self._events[job_id] = deque()
            return EnqueuedJob(id=job_id)

    async def get_status(self, job_id: UUID) -> JobStatus:
        return self._jobs[job_id]

    async def mark_enqueued(self, job_id: UUID) -> None:
        async with self._lock:
            job_status = self._jobs[job_id]
            self.job_transition_policy.validate(job_status, JobStatusCode.ENQUEUED)

            self._jobs[job_id] = JobStatus(
                id=job_status.id,
                status=JobStatusCode.ENQUEUED,
                result=job_status.result,
                error=job_status.error,
            )


def has_claim_expired(job_status: JobStatus) -> bool:
    current_unix_ts = datetime.datetime.now(tz=datetime.UTC).timestamp()
    if current_unix_ts > job_status.claim_expiration_unix_ts:
        return True
    return False


class InMemoryJobProcessingStore(JobProcessingStore):
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
        self.transition_policy = JobTransitionPolicy()

    async def claim_job(self, worker_id: str) -> ClaimedJob | None:
        """
        Querying is ineffective, but remember this is an in-memory POC
        :param worker_id:
        :return:
        """
        for job_id, job_status in self._jobs.items():
            if job_status.status == JobStatusCode.ENQUEUED:
                expiration_unix_ts = datetime.datetime.now(tz=datetime.UTC).timestamp() + 30
                await self._transition(
                    job_id, JobStatusCode.RUNNING, worker_id=worker_id, expiration_unix_ts=expiration_unix_ts
                )
                logger.info(f"Job {job_id} claimed by {worker_id}")
                return ClaimedJob(id=job_id, claim_type="enqueued", job_status=self._jobs[job_id])

            if job_status.status != JobStatusCode.RUNNING:
                continue
            claim_expired = has_claim_expired(job_status)
            if claim_expired:
                logger.info(f"Job {job_id} expired, originally assigned to {job_status.claimed_worker}")
                await self._transition(job_id, JobStatusCode.TIMED_OUT, worker_id=None)
                await self._transition(job_id, JobStatusCode.RETRYING)
                await self._transition(job_id, JobStatusCode.ENQUEUED)
                await self._transition(job_id, JobStatusCode.RUNNING, worker_id=worker_id)
                expiration_unix_ts = datetime.datetime.now(tz=datetime.UTC).timestamp() + 30
                await self._transition(
                    job_id, JobStatusCode.RUNNING, worker_id=worker_id, expiration_unix_ts=expiration_unix_ts
                )
                return ClaimedJob(id=job_id, claim_type="recovered", job_status=self._jobs[job_id])
        return None

    async def append_event(self, evt: JobEvent) -> None: ...

    async def heartbeat(self, job_id: UUID, worker_id: str) -> None:
        async with self._lock:
            job_status = self._jobs[job_id]
            if job_status.status != JobStatusCode.RUNNING:
                return None

            if job_status.claimed_worker != worker_id:
                return None

            updated_expiration_unix_ts = datetime.datetime.now(tz=datetime.UTC).timestamp() + 30

            self._jobs[job_id] = JobStatus(
                id=job_status.id,
                status=JobStatusCode.RUNNING,
                result=job_status.result,
                error=job_status.error,
                claimed_worker=worker_id,
                claim_expiration_unix_ts=updated_expiration_unix_ts,
                retry_count=job_status.retry_count,
            )
            return None

    async def set_failed(self, job_id: UUID, error: str) -> None:
        await self._transition(job_id, JobStatusCode.FAILED, error=error)

    async def set_succeeded(self, job_id: UUID, result: dict) -> None:
        await self._transition(job_id, JobStatusCode.SUCCEEDED, result=result)

    async def _transition(
        self,
        job_id: UUID,
        target_status: JobStatusCode,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        worker_id: str | None = None,
        updated_retry_count: int | None = None,
        expiration_unix_ts: int | None = None,
    ):
        async with self._lock:
            job_status = self._jobs[job_id]
            self.transition_policy.validate(job_status, target_status)
            self._jobs[job_id] = JobStatus(
                id=job_status.id,
                status=target_status,
                result=result or job_status.result,
                error=error or job_status.error,
                claimed_worker=worker_id or job_status.claimed_worker,
                claim_expiration_unix_ts=expiration_unix_ts or job_status.claim_expiration_unix_ts,
                retry_count=updated_retry_count or job_status.retry_count,
            )
