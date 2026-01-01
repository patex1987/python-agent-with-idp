import asyncio
import uuid
from typing import Protocol

import structlog

from agent_job_worker.in_memory.job_executor import AgentJobExecutor
from llm_agent.domain.agent.jobs.claim import ClaimedJob
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobProcessingStore

logger = structlog.get_logger(__name__)


class Consumer(Protocol):
    async def consume_and_execute_loop(self): ...

    async def shutdown_execution(self): ...


class InMemoryConsumer(Consumer):
    def __init__(
        self,
        job_store: JobProcessingStore,
        job_signal_queue: JobSignalQueue,
        worker_id: str,
        job_executor: AgentJobExecutor,
    ):
        logger.info("Initializing in-memory consumer", worker_id=worker_id)
        self.job_store = job_store
        self.job_signal_queue = job_signal_queue
        self._execution_allowed = True
        self.worker_id = worker_id
        self.job_lease_scope_factory = JobLeaseScope
        self.job_executor = job_executor

    async def consume_and_execute_loop(self):
        """
        TODO: refactor into smaller unit. Use the following at least:
            - consumer loop
            - job executor
            - execution policy
        TODO: implement the notifier and hook into relevant events
        TODO: add a concurrent health checker, so it's literally just
            checking if the worker is running
        """
        while self._execution_allowed:
            await self.job_signal_queue.wait()
            claimed_job = await self.job_store.claim_job(self.worker_id)
            if not claimed_job:
                continue

            logger.info(f"{self.worker_id}: claimed job", job_id=claimed_job.id)
            async with self.job_lease_scope_factory(
                worker_id=self.worker_id, job_id=claimed_job.id, job_store=self.job_store
            ):
                await self.execute_job(claimed_job=claimed_job)

    async def execute_job(self, *, claimed_job: ClaimedJob):
        job_id = claimed_job.id
        logger.info(f"{self.worker_id}: executing job", job_id=job_id)
        # await notifier.publish(JobEvent(job_id, "started", {}))

        try:
            await self.job_executor.execute(job_id, self.worker_id, self.job_store)

            logger.info(f"{self.worker_id}: job done", job_id=job_id)
            await self.job_store.set_succeeded(job_id, {"ok": True})
            # await notifier.publish(JobEvent(job_id, "succeeded", {}))
        except Exception as e:
            logger.error(f"{self.worker_id}: job failed", job_id=job_id, error=str(e))
            await self.job_store.set_failed(job_id, str(e))
            # await notifier.publish(JobEvent(job_id, "failed", {"error": str(e)}))

    async def shutdown_execution(self):
        self._execution_allowed = False


class JobLeaseScope:
    """
    Maintains job liveness while a worker is executing a claimed job.

    Responsibilities:
    - periodically renew the job lease via heartbeats
    - ensure the job is released if execution stops
    - scope liveness strictly to the execution lifetime

    Note: Do NOT add business timeouts here, that should be handled by
        the agent.
    """

    def __init__(self, worker_id: str, job_id: uuid.UUID, job_store: JobProcessingStore):
        self.worker_id = worker_id
        self.job_id = job_id
        self.job_store = job_store
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    async def __aenter__(self):
        self._running = True
        self._heartbeat_task = asyncio.create_task(self.heartbeat_loop(self.job_id))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def heartbeat_loop(self, job_id):
        heartbeat_interval = 5  # seconds
        while True:
            await asyncio.sleep(heartbeat_interval)
            logger.info(f"{self.worker_id}: heartbeat", job_id=job_id)
            await self.job_store.heartbeat(job_id, self.worker_id)
