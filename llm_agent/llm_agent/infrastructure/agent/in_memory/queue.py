import asyncio
from collections import deque
from uuid import UUID

from llm_agent.services.agent.queue import JobQueue


class InMemoryJobQueue(JobQueue):
    def __init__(self, internal_job_queue: deque[UUID]):
        self._internal_queue = internal_job_queue
        self._lock = asyncio.Lock()

    async def enqueue(self, job_id: UUID) -> None:
        """
        add a job to the queue
        """
        async with self._lock:
            self._internal_queue.append(job_id)

    async def claim_next(self, worker_id: str) -> UUID | None:
        """
        Worker is looking for a new job to execute

        TODO: verify the job state when claiming
        """
        async with self._lock:
            if not self._internal_queue:
                return None
            return self._internal_queue.popleft()

    async def heartbeat(self, job_id: UUID, worker_id: str) -> None:
        """
        TODO: to be implemented later
        """

        return
