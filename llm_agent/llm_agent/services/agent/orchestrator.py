import uuid

from llm_agent.domain.agent.jobs.entities import EnqueuedJob, JobRequest, JobStatus
from llm_agent.services.agent.queue import JobQueue
from llm_agent.services.agent.store import JobStore


class BackendJobOrchestrationService:
    def __init__(self, job_store: JobStore, job_queue: JobQueue):
        self.job_store = job_store
        self.job_queue = job_queue

    async def create_job(self, prompt: str) -> EnqueuedJob:
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
        enqueued_job = await self.job_store.create_job(
            job_request=job_request,
        )
        await self.job_queue.enqueue(enqueued_job.id)
        return enqueued_job

    async def get_job(self, job_id: str) -> JobStatus:
        job_status = await self.job_store.get_status(job_id=uuid.UUID(job_id))
        return job_status
