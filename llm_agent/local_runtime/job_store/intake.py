import asyncio
import uuid
from collections import deque
from uuid import UUID

from llm_agent.domain.agent.jobs.event import JobEvent
from llm_agent.domain.agent.jobs.exception import JobNotFoundError
from llm_agent.domain.agent.jobs.request import JobRequest
from llm_agent.domain.agent.jobs.status import JobStatus
from llm_agent.domain.agent.jobs.status_code import JobStatusCode, TERMINAL_JOB_STATUSES
from llm_agent.services.agent.store import JobIntakeStore
from llm_agent.services.agent.transition_policy import JobTransitionPolicy


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
            self._events[job_id].append(
                JobEvent(
                    job_id=job_id,
                    event_type="created",
                    payload={
                        "prompt": job_request.prompt,
                        "history": job_request.history,
                        "user_id": job_request.user_id,
                    },
                )
            )
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
            self._events[job_id].append(
                JobEvent(
                    job_id=job_id,
                    event_type="enqueued",
                    payload={},
                )
            )

    async def mark_cancelled(self, job_id: UUID) -> bool:
        """
        DEPRECATED
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
            self._events[job_id].append(
                JobEvent(
                    job_id=job_id,
                    event_type="cancel requested",
                    payload={},
                )
            )
            return True

    async def request_cancellation(self, job_id: UUID) -> bool:
        async with self._lock:
            if job_id not in self._jobs:
                raise JobNotFoundError(job_id=str(job_id))
            job_status = self._jobs[job_id]
            if job_status.status in TERMINAL_JOB_STATUSES:
                return False

            self._jobs[job_id] = JobStatus(
                id=job_status.id,
                status=job_status.status,
                result=job_status.result,
                error=job_status.error,
                cancel_requested=True,
                claimed_worker=job_status.claimed_worker,
                claim_expiration_unix_ts=job_status.claim_expiration_unix_ts,
                retry_count=job_status.retry_count,
            )
            self._events[job_id].append(
                JobEvent(
                    job_id=job_id,
                    event_type="cancel requested",
                    payload={},
                )
            )
            return True