from uuid import UUID

from llm_agent.domain.agent.jobs.event import JobEvent
from llm_agent.domain.agent.jobs.request import JobRequest
from llm_agent.domain.agent.jobs.status import JobStatus
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobIntakeStore


class BackendJobOrchestrationService:
    def __init__(
        self,
        job_store: JobIntakeStore,
        job_signal_queue: JobSignalQueue,
    ):
        self.job_store = job_store
        self.job_signal_queue = job_signal_queue

    async def create_job(self, prompt: str) -> JobStatus:
        """

        :param prompt:
        :return:
        """
        job_request = JobRequest(
            prompt=prompt,
            history=[],
            user_id="hardcoded_user_later_take_it_from_context",
        )
        created_job = await self.job_store.create_job(
            job_request=job_request,
        )
        await self.job_store.mark_enqueued(created_job.id)
        await self.job_signal_queue.notify()
        return created_job

    async def get_job(self, job_id: UUID) -> JobStatus:
        """
        Retrieve the job's status from the job store.

        :param job_id:
        :return: JobStatus
        :raises: JobNotFoundError
        """
        job_status = await self.job_store.get_status(job_id=job_id)
        return job_status

    async def cancel_job(self, job_id: UUID) -> bool:
        """
        Mark the job as canceled, notify the workers when the job state needs transition.

        :param job_id:
        :return:
        TODO: return proper domain objects instead of bool if needed
        """
        is_cancelled = await self.job_store.request_cancellation(job_id=job_id)
        if is_cancelled:
            await self.job_signal_queue.notify()

        return is_cancelled

    async def get_events(self, job_id: UUID, after_sequence: int | None = None) -> list[JobEvent]:
        """
        Retrieve events for a job from the job store's event log.

        :param job_id: The job ID
        :param after_sequence: Optional sequence number to filter events after
        :return: List of job events
        :raises: JobNotFoundError if the job is not found
        :raises: ValueError if event log is not available
        """
        return await self.job_store.get_events(job_id=job_id, after_sequence=after_sequence)
