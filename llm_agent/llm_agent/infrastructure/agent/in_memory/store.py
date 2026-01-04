import asyncio
import datetime
import uuid
from collections import deque
from uuid import UUID

import structlog

from agent_job_worker.domain.exception import JobLeaseLostError
from llm_agent.domain.agent.jobs.claim import ClaimedJob
from llm_agent.domain.agent.jobs.request import JobRequest
from llm_agent.domain.agent.jobs.status_code import JobStatusCode, TERMINAL_JOB_STATUSES
from llm_agent.domain.agent.jobs.status import JobStatus
from llm_agent.domain.agent.jobs.event import JobEvent
from llm_agent.domain.agent.jobs.exception import JobNotFoundError
from llm_agent.domain.agent.jobs.transition_request import TransitionRequestParams, get_value_or_fallback
from llm_agent.services.agent.store import JobIntakeStore, JobProcessingStore
from llm_agent.services.agent.transition_policy import JobTransitionPolicy


logger = structlog.getLogger(__name__)


class InMemoryJobIntakeStore(JobIntakeStore):
    def __init__(
        self,
        internal_job_storage: dict[UUID, JobStatus],
        internal_event_logs: dict[UUID, deque[JobEvent]],
        job_transition_policy: JobTransitionPolicy,
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
        self.job_transition_policy = job_transition_policy

    async def create_job(self, job_request: JobRequest) -> JobStatus:
        """

        :param job_request:
        :return:
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
            return job_status

    async def get_status(self, job_id: UUID) -> JobStatus:
        if job_id not in self._jobs:
            raise JobNotFoundError(job_id=str(job_id))
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

    async def mark_cancelled(self, job_id: UUID) -> bool:
        """

        :param job_id:
        :return:
        :raises: JobNotFoundError
        """
        async with self._lock:
            if job_id not in self._jobs:
                raise JobNotFoundError(job_id=str(job_id))
            job_status = self._jobs[job_id]
            if job_status.status in TERMINAL_JOB_STATUSES:
                return False

            self.job_transition_policy.validate(job_status, JobStatusCode.CANCELLED)

            self._jobs[job_id] = JobStatus(
                id=job_status.id,
                status=JobStatusCode.CANCELLED,
                result=job_status.result,
                error=job_status.error,
            )
            return True


def has_claim_expired(job_status: JobStatus) -> bool:
    if not job_status.claim_expiration_unix_ts:
        return False
    current_unix_ts = datetime.datetime.now(tz=datetime.UTC).timestamp()
    if current_unix_ts > job_status.claim_expiration_unix_ts:
        return True
    return False


async def get_new_expiration_ts() -> float:
    expiration_unix_ts = datetime.datetime.now(tz=datetime.UTC).timestamp() + 30
    return expiration_unix_ts


class InMemoryJobProcessingStore(JobProcessingStore):
    def __init__(
        self,
        internal_job_storage: dict[UUID, JobStatus],
        internal_event_logs: dict[UUID, deque[JobEvent]],
        job_transition_policy: JobTransitionPolicy,
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
        self.job_transition_policy = job_transition_policy

    async def claim_job(self, worker_id: str) -> ClaimedJob | None:
        """
        Querying is ineffective, but remember this is an in-memory POC

        Needs to be atomic to handle concurrency on multiple workers

        :param worker_id:
        :return:
        """
        async with self._lock:
            for job_id, job_status in self._jobs.items():
                if job_status.status != JobStatusCode.RUNNING:
                    continue
                claim_expired = has_claim_expired(job_status)
                if not claim_expired:
                    continue
                logger.info(f"Job claim on {job_id} expired, retrying")
                await self.recover_expired_jobs(job_id, job_status, worker_id)

            for job_id, job_status in self._jobs.items():
                if job_status.status == JobStatusCode.ENQUEUED:
                    expiration_unix_ts = await get_new_expiration_ts()
                    transition_request = TransitionRequestParams(
                        worker_id=worker_id, expiration_unix_ts=expiration_unix_ts
                    )
                    await self._transition_locked(job_id, JobStatusCode.RUNNING, transition_request=transition_request)
                    logger.info(f"Job {job_id} claimed by {worker_id}")
                    return ClaimedJob(id=job_id, claim_type="enqueued", job_status=self._jobs[job_id])

            return None

    async def append_event(self, evt: JobEvent) -> None: ...

    async def heartbeat(self, job_id: UUID, worker_id: str) -> JobStatusCode:
        """
        Extend the expiration time of a running job claimed by a given worker.

        :param job_id:
        :param worker_id:
        :return:
        :raises: JobLeaseLostError - when the job is claimed by a different worker
        """
        async with self._lock:
            job_status = self._jobs[job_id]

            if job_status.status == JobStatusCode.CANCELLED:
                return JobStatusCode.CANCELLED

            if job_status.status != JobStatusCode.RUNNING:
                return job_status.status

            if job_status.claimed_worker != worker_id:
                raise JobLeaseLostError(f"Job {job_id} is not claimed by {worker_id}")

            updated_expiration_unix_ts = await get_new_expiration_ts()

            self._jobs[job_id] = JobStatus(
                id=job_status.id,
                status=JobStatusCode.RUNNING,
                result=job_status.result,
                error=job_status.error,
                claimed_worker=worker_id,
                claim_expiration_unix_ts=updated_expiration_unix_ts,
                retry_count=job_status.retry_count,
            )
            return JobStatusCode.RUNNING

    async def set_failed(self, job_id: UUID, error: str) -> None:
        async with self._lock:
            transition_request = TransitionRequestParams(error=error)
            await self._transition_locked(job_id, JobStatusCode.FAILED, transition_request=transition_request)

    async def set_succeeded(self, job_id: UUID, result: dict) -> None:
        async with self._lock:
            transition_request = TransitionRequestParams(result=result)
            await self._transition_locked(job_id, JobStatusCode.SUCCEEDED, transition_request=transition_request)

    async def _transition_locked(
        self,
        job_id: UUID,
        target_status: JobStatusCode,
        *,
        transition_request: TransitionRequestParams | None = None,
    ):
        """
        Transition the job to the desired state.

        Expects that a lock is held over the given entity.
        :param job_id:
        :param target_status:
        :param transition_request:
        :return:
        """
        job_status = self._jobs[job_id]
        if not transition_request:
            transition_request = TransitionRequestParams()

        self.job_transition_policy.validate(job_status, target_status)

        result = get_value_or_fallback(transition_request.result, job_status.result)
        error = get_value_or_fallback(transition_request.error, job_status.error)
        worker_id = get_value_or_fallback(transition_request.worker_id, job_status.claimed_worker)
        claim_expiration_unix_ts = get_value_or_fallback(
            transition_request.expiration_unix_ts, job_status.claim_expiration_unix_ts
        )
        retry_count = get_value_or_fallback(transition_request.retry_count, job_status.retry_count)

        self._jobs[job_id] = JobStatus(
            id=job_status.id,
            status=target_status,
            result=result,
            error=error,
            claimed_worker=worker_id,
            claim_expiration_unix_ts=claim_expiration_unix_ts,
            retry_count=retry_count,
        )

    async def recover_expired_jobs(self, job_id, job_status, worker_id):
        logger.info(f"Job {job_id} expired, originally assigned to {job_status.claimed_worker}")
        transition_request = TransitionRequestParams(worker_id=worker_id)
        await self._transition_locked(job_id, JobStatusCode.TIMED_OUT, transition_request=transition_request)
        updated_retry = TransitionRequestParams(worker_id=worker_id, retry_count=job_status.retry_count + 1)
        await self._transition_locked(job_id, JobStatusCode.RETRYING, transition_request=updated_retry)
        await self._transition_locked(job_id, JobStatusCode.ENQUEUED, transition_request=transition_request)
