import uuid

from llm_agent.domain.agent.jobs.request import JobRequest
from llm_agent.domain.agent.jobs.status import JobStatus
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobIntakeStore


class BackendJobOrchestrationService:
    def __init__(self, job_store: JobIntakeStore, job_signal_queue: JobSignalQueue):
        self.job_store = job_store
        self.job_signal_queue = job_signal_queue

    async def create_job(self, prompt: str) -> JobStatus:
        """

        :param prompt:
        :return:

        TODO: move the job status to CREATED when enqueuing
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

    async def get_job(self, job_id: str) -> JobStatus:
        job_status = await self.job_store.get_status(job_id=uuid.UUID(job_id))
        return job_status
